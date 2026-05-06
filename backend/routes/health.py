# backend/app/routes/health.py
"""
Health check route for monitoring service status.
Verifies connectivity to all external services (MongoDB, MinIO).

✅ REFACTORED:
  - Access services via request.app.state
  - Removed module-level service assignments
  - Active health checks for all dependencies
  - Comprehensive error handling and logging
  - Detailed status reporting
  - Fixed MinIO list_buckets() async/sync handling
"""
import asyncio
import logging
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel, Field

from config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== RESPONSE MODELS ====================
class ServiceStatus(BaseModel):
    """Individual service status."""
    status: str = Field(..., description="Service status (healthy, unhealthy)")
    latency_ms: Optional[float] = Field(None, description="Response time in milliseconds")
    version: Optional[str] = Field(None, description="Service version")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


class HealthCheckResponse(BaseModel):
    """Overall health check response."""
    status: str = Field(..., description="Overall status (healthy, degraded, unhealthy)")
    timestamp: str = Field(..., description="Check timestamp (ISO 8601)")
    duration_ms: Optional[float] = Field(None, description="Check duration in milliseconds")
    services: dict[str, ServiceStatus] = Field(..., description="Individual service statuses")
    version: str = Field(..., description="API version")
    environment: str = Field(..., description="Environment name")


# ==================== HELPER FUNCTIONS ====================
async def check_mongodb_health(mongo_client) -> tuple[str, Optional[str], Optional[float]]:
    """
    Check MongoDB connectivity and health.

    Args:
        mongo_client: MongoDB client

    Returns:
        Tuple of (status, version, latency_ms)
    """
    if mongo_client is None:
        logger.warning("⚠️  MongoDB client not initialized")
        return "unhealthy", None, None

    try:
        start_time = time.time()

        # Wrap blocking call with asyncio.to_thread for async compatibility
        server_info = await asyncio.wait_for(
            asyncio.to_thread(mongo_client.server_info),
            timeout=5.0
        )

        latency = (time.time() - start_time) * 1000
        version = server_info.get("version", "unknown")

        logger.debug(f"✅ MongoDB healthy (latency: {latency:.0f}ms, version: {version})")
        return "healthy", version, latency

    except asyncio.TimeoutError:
        logger.warning("⚠️  MongoDB health check timeout (5s)")
        return "unhealthy", None, None

    except Exception as e:
        logger.warning(f"⚠️  MongoDB health check failed: {type(e).__name__}: {e}")
        return "unhealthy", None, None


async def check_minio_health(minio_client) -> tuple[str, Optional[str], Optional[float]]:
    """
    Check MinIO connectivity and health.

    Args:
        minio_client: MinIO client wrapper

    Returns:
        Tuple of (status, bucket_count, latency_ms)
    """
    if minio_client is None:
        logger.warning("⚠️  MinIO client not initialized")
        return "unhealthy", None, None

    try:
        start_time = time.time()

        # ✅ FIX: Access the underlying Minio client and call list_buckets()
        # MinIO SDK's list_buckets() is a synchronous blocking call
        if not hasattr(minio_client, 'client'):
            logger.warning("⚠️  MinIO wrapper missing 'client' attribute")
            return "unhealthy", None, None

        # Wrap blocking call with asyncio.to_thread for async compatibility
        buckets = await asyncio.wait_for(
            asyncio.to_thread(minio_client.client.list_buckets),
            timeout=5.0
        )

        latency = (time.time() - start_time) * 1000
        bucket_count = len(list(buckets)) if buckets else 0

        logger.debug(f"✅ MinIO healthy (latency: {latency:.0f}ms, buckets: {bucket_count})")
        return "healthy", str(bucket_count), latency

    except asyncio.TimeoutError:
        logger.warning("⚠️  MinIO health check timeout (5s)")
        return "unhealthy", None, None

    except Exception as e:
        logger.warning(f"⚠️  MinIO health check failed: {type(e).__name__}: {e}")
        return "unhealthy", None, None


async def check_form_processor_health(form_processor) -> tuple[str, Optional[str]]:
    """
    Check FormProcessor initialization status.

    Args:
        form_processor: FormProcessor instance

    Returns:
        Tuple of (status, error_message)
    """
    if form_processor is None:
        logger.warning("⚠️  FormProcessor not initialized")
        return "unhealthy", "FormProcessor not initialized"

    try:
        # Check if processor has required attributes
        if not hasattr(form_processor, "process"):
            return "unhealthy", "FormProcessor missing 'process' method"

        if not hasattr(form_processor, "storage_service"):
            return "unhealthy", "FormProcessor missing storage service"

        logger.debug("✅ FormProcessor healthy")
        return "healthy", None

    except Exception as e:
        logger.warning(f"⚠️  FormProcessor check failed: {type(e).__name__}: {e}")
        return "unhealthy", str(e)


# ==================== ROUTES ====================
@router.get(
    "/",
    response_model=HealthCheckResponse,
    summary="Health check endpoint",
    tags=["health"]
)
async def health_check(request: Request) -> HealthCheckResponse:
    """
    Comprehensive health check of all services.

    Performs active checks on MongoDB, MinIO, and FormProcessor
    to ensure all components are operational. Used for monitoring
    and load balancer health checks.

    **Response:**
    - status: Overall health (healthy, degraded, unhealthy)
    - timestamp: Check timestamp (ISO 8601)
    - duration_ms: Total check duration in milliseconds
    - services: Individual service statuses with latency
    - version: API version
    - environment: Running environment (development, production)

    **Service Statuses:**
    - api: Application server status
    - mongodb: Database connectivity
    - minio: Object storage connectivity
    - form_processor: Form processing service availability

    **Status Codes:**
    - 200: All services healthy
    - 503: One or more services degraded/unhealthy

    **Examples:**
    ```bash
    # Basic health check
    curl https://localhost:6443/api/health/

    # From Docker health check
    curl --fail https://localhost:6443/api/health/ || exit 1
    ```
    """

    check_start = time.time()
    logger.debug("🏥 Health check initiated")

    try:
        # ✅ Access services from app.state (type-safe container)
        services = request.app.state.services
        mongo_client = request.app.state.mongo
        minio_client = request.app.state.minio
        form_processor = request.app.state.form_processor

        if services is None:
            logger.error("❌ Services container not initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Services not initialized"
            )

        # ==================== CHECK ALL SERVICES ====================
        service_statuses = {}

        # API status (always healthy if we reached this point)
        service_statuses["api"] = ServiceStatus(
            status="healthy",
            latency_ms=0.0,
        )

        # MongoDB status
        db_status, db_version, db_latency = await check_mongodb_health(mongo_client)
        service_statuses["mongodb"] = ServiceStatus(
            status=db_status,
            version=db_version,
            latency_ms=db_latency,
            error=None if db_status == "healthy" else "Connection failed",
        )

        # MinIO status - ✅ FIXED: Proper async handling of list_buckets()
        minio_status, minio_bucket_count, minio_latency = await check_minio_health(minio_client)
        service_statuses["minio"] = ServiceStatus(
            status=minio_status,
            version=minio_bucket_count,  # Shows bucket count instead of bucket name
            latency_ms=minio_latency,
            error=None if minio_status == "healthy" else "Connection failed",
        )

        # FormProcessor status
        processor_status, processor_error = await check_form_processor_health(form_processor)
        service_statuses["form_processor"] = ServiceStatus(
            status=processor_status,
            error=processor_error,
        )

        # ==================== DETERMINE OVERALL STATUS ====================
        unhealthy_services = [
            name for name, svc in service_statuses.items()
            if svc.status == "unhealthy"
        ]

        # Don't count "api" as critical for overall status
        unhealthy_critical = [
            name for name in unhealthy_services
            if name != "api"
        ]

        if not unhealthy_critical:
            overall_status = "healthy"
            http_status = status.HTTP_200_OK
        elif len(unhealthy_critical) == 1:
            overall_status = "degraded"
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
        else:
            overall_status = "unhealthy"
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE

        check_duration = (time.time() - check_start) * 1000

        logger.info(
            f"✅ Health check completed: {overall_status} "
            f"(duration: {check_duration:.0f}ms)"
        )

        if unhealthy_critical:
            logger.warning(f"⚠️  Unhealthy services: {', '.join(unhealthy_critical)}")

        response = HealthCheckResponse(
            status=overall_status,
            timestamp=datetime.utcnow().isoformat(),
            duration_ms=check_duration,
            services=service_statuses,
            version=settings.API_VERSION,
            environment=settings.ENVIRONMENT,
        )

        # Return with appropriate status code
        if http_status != status.HTTP_200_OK:
            raise HTTPException(
                status_code=http_status,
                detail=f"Services unhealthy: {', '.join(unhealthy_critical)}"
            )

        return response

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"❌ Health check failed: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}"
        )


@router.get(
    "/live",
    summary="Liveness probe",
    tags=["health"]
)
async def liveness_probe(request: Request) -> dict:
    """
    Kubernetes liveness probe endpoint.

    Returns 200 if the application is running.
    Used by Kubernetes to determine if the container should be restarted.

    **Response:**
    - status: Always "alive" if endpoint is reachable
    - timestamp: Current timestamp

    **Example:**
    ```bash
    curl https://localhost:6443/api/health/live
    ```
    """
    logger.debug("💚 Liveness probe")
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get(
    "/ready",
    summary="Readiness probe",
    tags=["health"]
)
async def readiness_probe(request: Request) -> dict:
    """
    Kubernetes readiness probe endpoint.

    Returns 200 only if the application is ready to serve traffic.
    Checks critical service dependencies.

    **Response:**
    - status: "ready" if all critical services are available
    - ready: Boolean indicating readiness
    - timestamp: Current timestamp

    **Errors:**
    - 503: Services not ready

    **Example:**
    ```bash
    curl https://localhost:6443/api/health/ready
    ```
    """
    logger.debug("🟢 Readiness probe")

    try:
        # Access services from app.state
        mongo_client = request.app.state.mongo
        minio_client = request.app.state.minio
        form_processor = request.app.state.form_processor

        # Check critical services exist
        is_ready = all([
            mongo_client is not None,
            minio_client is not None,
            form_processor is not None,
        ])

        if is_ready:
            logger.debug("✅ Application is ready")
            return {
                "status": "ready",
                "ready": True,
                "timestamp": datetime.utcnow().isoformat(),
            }
        else:
            missing = []
            if mongo_client is None:
                missing.append("mongodb")
            if minio_client is None:
                missing.append("minio")
            if form_processor is None:
                missing.append("form_processor")

            logger.warning(f"⚠️  Application not ready - missing: {', '.join(missing)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Services not initialized: {', '.join(missing)}"
            )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"❌ Readiness check failed: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Readiness check failed"
        )


@router.get(
    "/startup",
    summary="Startup probe",
    tags=["health"]
)
async def startup_probe(request: Request) -> dict:
    """
    Kubernetes startup probe endpoint.

    Returns 200 when the application has completed startup.
    Kubernetes waits for this before other probes.

    **Response:**
    - status: "started" when ready
    - started: Boolean indicating startup completion
    - timestamp: Current timestamp

    **Errors:**
    - 503: Still starting up

    **Example:**
    ```bash
    curl https://localhost:6443/api/health/startup
    ```
    """
    logger.debug("🚀 Startup probe")

    try:
        # Access services from app.state
        services = request.app.state.services

        if services is None:
            logger.warning("⚠️  Services not yet initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Application still starting up"
            )

        logger.debug("✅ Startup complete")
        return {
            "status": "started",
            "started": True,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"❌ Startup check failed: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Startup check failed"
        )

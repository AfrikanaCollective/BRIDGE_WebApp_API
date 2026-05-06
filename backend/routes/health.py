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
"""
import asyncio
import logging
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
    uptime_seconds: Optional[float] = Field(None, description="Application uptime")
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
    try:
        start_time = datetime.utcnow()
        health_result = await mongo_client.health_check()
        latency = (datetime.utcnow() - start_time).total_seconds() * 1000

        if health_result.get("connected"):
            version = health_result.get("server_info", {}).get("version", "unknown")
            logger.debug(f"✅ MongoDB healthy (latency: {latency:.0f}ms)")
            return "healthy", version, latency
        else:
            error = health_result.get("error", "Unknown error")
            logger.warning(f"⚠️  MongoDB unhealthy: {error}")
            return "unhealthy", None, latency

    except asyncio.TimeoutError:
        logger.warning("⚠️  MongoDB health check timeout")
        return "unhealthy", None, None
    except Exception as e:
        logger.warning(f"⚠️  MongoDB health check failed: {e}")
        return "unhealthy", None, None


async def check_minio_health(minio_client) -> tuple[str, Optional[str], Optional[float]]:
    """
    Check MinIO connectivity and health.

    Args:
        minio_client: MinIO client

    Returns:
        Tuple of (status, bucket_name, latency_ms)
    """
    try:
        start_time = datetime.utcnow()

        # Attempt to list buckets
        await minio_client.list_buckets()
        latency = (datetime.utcnow() - start_time).total_seconds() * 1000

        bucket = getattr(minio_client, "bucket_name", "unknown")
        logger.debug(f"✅ MinIO healthy (latency: {latency:.0f}ms)")
        return "healthy", bucket, latency

    except asyncio.TimeoutError:
        logger.warning("⚠️  MinIO health check timeout")
        return "unhealthy", None, None
    except Exception as e:
        logger.warning(f"⚠️  MinIO health check failed: {e}")
        return "unhealthy", None, None


async def check_form_processor_health(form_processor) -> tuple[str, Optional[str]]:
    """
    Check FormProcessor initialization status.

    Args:
        form_processor: FormProcessor instance

    Returns:
        Tuple of (status, error_message)
    """
    try:
        if form_processor is None:
            return "unhealthy", "FormProcessor not initialized"

        # Check if processor has required attributes
        if not hasattr(form_processor, "storage_service"):
            return "unhealthy", "FormProcessor missing storage service"

        logger.debug("✅ FormProcessor healthy")
        return "healthy", None

    except Exception as e:
        logger.warning(f"⚠️  FormProcessor check failed: {e}")
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
    curl http://localhost:6000/api/health/

    # From Docker health check
    curl --fail https://localhost:6443/api/health/ || exit 1
    ```
    """

    check_start = datetime.utcnow()
    logger.debug("🏥 Health check initiated")

    try:
        # ✅ CHANGE 1: Access services from app.state
        services = request.app.state.services
        mongo_client = request.app.state.mongo
        minio_client = request.app.state.minio
        form_processor = request.app.state.form_processor

        if not services:
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
        if mongo_client:
            db_status, db_version, db_latency = await check_mongodb_health(mongo_client)
            service_statuses["mongodb"] = ServiceStatus(
                status=db_status,
                version=db_version,
                latency_ms=db_latency,
                error="Connection failed" if db_status == "unhealthy" else None,
            )
        else:
            service_statuses["mongodb"] = ServiceStatus(
                status="unhealthy",
                error="MongoDB client not initialized",
            )

        # MinIO status
        if minio_client:
            minio_status, minio_bucket, minio_latency = await check_minio_health(minio_client)
            service_statuses["minio"] = ServiceStatus(
                status=minio_status,
                version=minio_bucket,
                latency_ms=minio_latency,
                error="Connection failed" if minio_status == "unhealthy" else None,
            )
        else:
            service_statuses["minio"] = ServiceStatus(
                status="unhealthy",
                error="MinIO client not initialized",
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

        if not unhealthy_services:
            overall_status = "healthy"
            http_status = status.HTTP_200_OK
        else:
            overall_status = "degraded" if len(unhealthy_services) < 2 else "unhealthy"
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE

        check_duration = (datetime.utcnow() - check_start).total_seconds() * 1000

        logger.info(
            f"✅ Health check completed: {overall_status} "
            f"(duration: {check_duration:.0f}ms)"
        )

        if unhealthy_services:
            logger.warning(f"⚠️  Unhealthy services: {', '.join(unhealthy_services)}")

        response = HealthCheckResponse(
            status=overall_status,
            timestamp=check_start.isoformat(),
            services=service_statuses,
            version=settings.API_VERSION,
            environment=settings.ENVIRONMENT,
        )

        # Return with appropriate status code
        if http_status != status.HTTP_200_OK:
            # We need to return the response but with a 503 status
            # FastAPI doesn't support this with response_model, so we raise
            raise HTTPException(
                status_code=http_status,
                detail="One or more services are unhealthy"
            )

        return response

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"❌ Health check failed: {e}", exc_info=True)
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
    curl http://localhost:6000/api/health/live
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
    curl http://localhost:6000/api/health/ready
    ```
    """
    logger.debug("🟢 Readiness probe")

    try:
        # ✅ CHANGE 2: Access services from app.state
        mongo_client = request.app.state.mongo
        minio_client = request.app.state.minio
        form_processor = request.app.state.form_processor

        # Check critical services
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
            logger.warning("⚠️  Application not ready - services missing")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Services not initialized"
            )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"❌ Readiness check failed: {e}")
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
    curl http://localhost:6000/api/health/startup
    ```
    """
    logger.debug("🚀 Startup probe")

    try:
        # ✅ CHANGE 3: Access services from app.state
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
        logger.error(f"❌ Startup check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Startup check failed"
        )

# backend/routes/health.py
"""Health check route with robust error handling."""
import asyncio
import logging
import time
from datetime import datetime
from typing import Optional
from models.health import ServiceStatus, HealthCheckResponse

from fastapi import APIRouter, Request, HTTPException, status

from config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter()


# ==================== HELPER FUNCTIONS ====================
async def check_mongodb_health(mongo_client) -> tuple[str, Optional[str], Optional[float]]:
    """
    Check MongoDB connectivity and health.

    Uses the new async health_check() method on MongoClient.
    """
    if mongo_client is None:
        logger.warning("⚠️  MongoDB client not initialized")
        return "unhealthy", None, None

    try:
        start_time = time.time()

        # Use the new async health_check method with timeout
        health = await mongo_client.health_check(timeout=5.0)

        latency = (time.time() - start_time) * 1000

        if health["connected"]:
            version = health.get("version", "unknown")
            logger.debug(f"✅ MongoDB healthy (latency: {latency:.0f}ms, version: {version})")
            return "healthy", version, latency
        else:
            error = health.get("error", "Unknown error")
            logger.warning(f"⚠️  MongoDB unhealthy: {error}")
            return "unhealthy", None, latency

    except Exception as e:
        logger.error(f"⚠️  MongoDB health check exception: {type(e).__name__}: {e}")
        return "unhealthy", None, None


async def check_minio_health(minio_client) -> tuple[str, Optional[str], Optional[float]]:
    """
    Check MinIO connectivity and health.

    Handles both direct Minio client and wrapper implementations.
    """
    if minio_client is None:
        logger.warning("⚠️  MinIO client not initialized")
        return "unhealthy", None, None

    try:
        start_time = time.time()

        bucket_count = 0

        # Method 1: Wrapper with client attribute
        if hasattr(minio_client, 'client'):
            buckets = await asyncio.wait_for(
                asyncio.to_thread(minio_client.client.list_buckets),
                timeout=5.0
            )
            bucket_count = len(list(buckets)) if buckets else 0

        # Method 2: Direct list_buckets on client
        elif hasattr(minio_client, 'list_buckets'):
            buckets = await asyncio.wait_for(
                asyncio.to_thread(minio_client.list_buckets),
                timeout=5.0
            )
            bucket_count = len(list(buckets)) if buckets else 0

        else:
            logger.warning("⚠️  MinIO client has no list_buckets method")
            return "unhealthy", None, None

        latency = (time.time() - start_time) * 1000
        logger.debug(f"✅ MinIO healthy (latency: {latency:.0f}ms, buckets: {bucket_count})")
        return "healthy", str(bucket_count), latency

    except asyncio.TimeoutError:
        logger.warning("⚠️  MinIO health check timeout (5s)")
        return "unhealthy", None, None

    except Exception as e:
        logger.warning(f"⚠️  MinIO health check failed: {type(e).__name__}: {e}")
        return "unhealthy", None, None


async def check_form_processor_health(form_processor) -> tuple[str, Optional[str], dict]:
    """
    Check FormProcessor initialization status with detailed diagnostics.

    Returns:
        tuple: (status, error_message, details_dict)
    """
    details = {
        "has_process_method": False,
        "has_storage_service": False,
        "storage_service_initialized": False,
        "has_mongo_client": False,
        "has_ssl_context": False,
        "attributes": [],
    }

    if form_processor is None:
        logger.warning("⚠️  FormProcessor is None")
        return "unhealthy", "FormProcessor not initialized", details

    try:
        # ==================== CHECK PROCESS METHOD ====================
        if not hasattr(form_processor, "process"):
            logger.error("❌ FormProcessor missing 'process' method")
            details["attributes"] = [attr for attr in dir(form_processor) if not attr.startswith("_")]
            return "unhealthy", "Missing 'process' method", details

        details["has_process_method"] = True
        logger.debug("✅ FormProcessor has 'process' method")

        # ==================== CHECK STORAGE SERVICE ====================
        if not hasattr(form_processor, "storage_service"):
            logger.error("❌ FormProcessor missing 'storage_service' attribute")
            details["attributes"] = [attr for attr in dir(form_processor) if not attr.startswith("_")]
            return "unhealthy", "Missing 'storage_service' attribute", details

        details["has_storage_service"] = True
        logger.debug("✅ FormProcessor has 'storage_service' attribute")

        # Check if storage_service is actually initialized
        if form_processor.storage_service is None:
            logger.error("❌ FormProcessor storage_service is None")
            return "unhealthy", "storage_service not initialized", details

        details["storage_service_initialized"] = True
        logger.debug("✅ FormProcessor storage_service is initialized")

        # ==================== CHECK STORAGE SERVICE METHODS ====================
        storage = form_processor.storage_service
        required_methods = [
            "save_form_processing_result",
            "save_form_document",
        ]
        missing_methods = [
            method for method in required_methods
            if not hasattr(storage, method)
        ]

        if missing_methods:
            logger.error(f"❌ StorageService missing methods: {missing_methods}")
            return (
                "unhealthy",
                f"StorageService incomplete: missing {missing_methods}",
                details
            )

        logger.debug("✅ StorageService has all required methods")

        # ==================== CHECK MONGO CLIENT ====================
        if hasattr(form_processor, "mongo_client"):
            details["has_mongo_client"] = form_processor.mongo_client is not None
            if form_processor.mongo_client is not None:
                logger.debug("✅ FormProcessor has mongo_client")
            else:
                logger.debug("⚠️  FormProcessor mongo_client is None")
        else:
            logger.debug("⚠️  FormProcessor missing mongo_client attribute")

        # ==================== CHECK SSL CONTEXT ====================
        if hasattr(form_processor, "ssl_context"):
            details["has_ssl_context"] = form_processor.ssl_context is not None
            if form_processor.ssl_context is not None:
                logger.debug("✅ FormProcessor has ssl_context")
            else:
                logger.debug("⚠️  FormProcessor ssl_context is None")
        else:
            logger.debug("⚠️  FormProcessor missing ssl_context attribute")

        # ==================== FINAL CHECK ====================
        logger.debug("✅ FormProcessor health check passed")
        return "healthy", None, details

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.error(f"❌ FormProcessor health check exception: {error_msg}")
        details["error"] = error_msg
        details["attributes"] = [attr for attr in dir(form_processor) if not attr.startswith("_")]
        return "unhealthy", error_msg, details


# ==================== ROUTES ====================
@router.get(
    "",
    response_model=HealthCheckResponse,
    summary="Health check endpoint",
    tags=["health"]
)
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
    to ensure all components are operational.

    **Status Codes:**
    - 200: All services healthy
    - 503: One or more services degraded/unhealthy
    """
    check_start = time.time()
    logger.debug("🏥 Health check initiated")

    try:
        # ==================== ACCESS SERVICES ====================
        services = getattr(request.app.state, "services", None)
        mongo_client = getattr(request.app.state, "mongo", None)
        minio_client = getattr(request.app.state, "minio", None)
        form_processor = getattr(request.app.state, "form_processor", None)

        if services is None:
            logger.error("❌ Services container not initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Services not initialized"
            )

        # ==================== CHECK ALL SERVICES ====================
        service_statuses = {}

        # ========== API STATUS ==========
        # API status (always healthy if we reached this point)
        service_statuses["api"] = ServiceStatus(
            status="healthy",
            latency_ms=0.0,
        )
        logger.debug("✅ API status: healthy")

        # ========== MONGODB STATUS ==========
        logger.debug("🔍 Checking MongoDB...")
        db_status, db_version, db_latency = await check_mongodb_health(mongo_client)
        service_statuses["mongodb"] = ServiceStatus(
            status=db_status,
            version=db_version,
            latency_ms=db_latency,
            error=None if db_status == "healthy" else "Connection failed",
        )
        logger.debug(f"📊 MongoDB status: {db_status}")

        # ========== MINIO STATUS ==========
        logger.debug("🔍 Checking MinIO...")
        minio_status, minio_bucket_count, minio_latency = await check_minio_health(minio_client)
        service_statuses["minio"] = ServiceStatus(
            status=minio_status,
            version=minio_bucket_count,
            latency_ms=minio_latency,
            error=None if minio_status == "healthy" else "Connection failed",
        )
        logger.debug(f"📊 MinIO status: {minio_status}")

        # ========== FORM PROCESSOR STATUS ==========
        logger.debug("🔍 Checking FormProcessor...")
        processor_status, processor_error, processor_details = await check_form_processor_health(
            form_processor
        )
        service_statuses["form_processor"] = ServiceStatus(
            status=processor_status,
            error=processor_error,
            details=processor_details,
        )
        logger.debug(f"📊 FormProcessor status: {processor_status}")
        if processor_error:
            logger.debug(f"   Error: {processor_error}")
        if processor_details:
            logger.debug(f"   Details: {processor_details}")

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


@router.get("/live", tags=["health"])
async def liveness_probe(request: Request) -> dict:
    """Kubernetes liveness probe - returns 200 if app is running."""
    logger.debug("💚 Liveness probe")
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/ready", tags=["health"])
async def readiness_probe(request: Request) -> dict:
    """Kubernetes readiness probe - returns 200 if ready to serve."""
    logger.debug("🟢 Readiness probe")

    try:
        # ==================== SAFE ATTRIBUTE ACCESS ====================
        mongo_client = getattr(request.app.state, "mongo", None)
        minio_client = getattr(request.app.state, "minio", None)
        form_processor = getattr(request.app.state, "form_processor", None)

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


@router.get("/startup", tags=["health"])
async def startup_probe(request: Request) -> dict:
    """Kubernetes startup probe - returns 200 when startup is complete."""
    logger.debug("🚀 Startup probe")

    try:
        # ==================== SAFE ATTRIBUTE ACCESS ====================
        services = getattr(request.app.state, "services", None)

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
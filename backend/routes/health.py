# backend/app/routes/health.py
import logging
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/health", tags=["health"])

# Dependencies
services = {}


def set_services(**kwargs):
    """Set service instances for health checks"""
    services.update(kwargs)


@router.get("")
async def health_check():
    """
    Check overall health of all services
    """
    health_status = {
        "status": "healthy",
        "services": {}
    }

    try:
        # Check MongoDB
        mongo_client = services.get("mongo_client")
        if mongo_client:
            mongo_health = mongo_client.health_check()
            health_status["services"]["mongodb"] = "healthy" if mongo_health else "unhealthy"
            if not mongo_health:
                health_status["status"] = "degraded"

        # Check Qwen
        qwen_client = services.get("qwen_client")
        if qwen_client:
            health_status["services"]["qwen"] = "reachable"

        # Check MinIO
        minio_client = services.get("minio_client")
        if minio_client:
            health_status["services"]["minio"] = "available"

        return health_status

    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/detailed")
async def detailed_health_check():
    """
    Detailed health check with response times
    """
    import time

    detailed_status = {
        "timestamp": str(time.time()),
        "services": {}
    }

    # Check each service with timing
    services_to_check = [
        ("mongodb", services.get("mongo_client"), "health_check"),
    ]

    for service_name, service_instance, check_method in services_to_check:
        if service_instance:
            start_time = time.time()
            try:
                if hasattr(service_instance, check_method):
                    result = getattr(service_instance, check_method)()
                    response_time = (time.time() - start_time) * 1000
                    detailed_status["services"][service_name] = {
                        "status": "healthy" if result else "unhealthy",
                        "response_time_ms": response_time
                    }
            except Exception as e:
                detailed_status["services"][service_name] = {
                    "status": "error",
                    "error": str(e)
                }

    return detailed_status

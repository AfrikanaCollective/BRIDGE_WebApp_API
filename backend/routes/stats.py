# backend/routes/stats.py

"""
Statistics and aggregate data routes.
"""

import logging
from fastapi import APIRouter, Request, HTTPException, status
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()


# ==================== RESPONSE MODELS ====================
class ProcessingTimeStats(BaseModel):
    """Processing time statistics."""
    average: float = Field(..., description="Average processing time in ms")
    max: int = Field(..., description="Maximum processing time in ms")
    min: int = Field(..., description="Minimum processing time in ms")


class StatsOverview(BaseModel):
    """Aggregate statistics overview."""
    period_days: int = Field(..., description="Number of days in the period")
    date_range: Dict[str, str] = Field(..., description="Start and end dates")
    total_processed: int = Field(..., description="Total forms processed")
    by_status: Dict[str, int] = Field(..., description="Count by status")
    by_form_type: Dict[str, int] = Field(..., description="Count by form type")
    processing_time_ms: ProcessingTimeStats = Field(..., description="Processing time stats")
    success_rate: float = Field(..., description="Percentage of successful completions")


# ==================== HELPER FUNCTIONS ====================
def get_mongo_client(request: Request):
    """
    ✅ FIXED: Validate MongoDB client is available.

    This function checks request.app.state for the mongo client
    that was set during app initialization.
    """
    # Try multiple possible locations (in case of different naming)
    mongo = getattr(request.app.state, 'mongo', None)

    if not mongo:
        logger.error("❌ MongoDB client not initialized in app.state")
        logger.debug(f"Available app.state attributes: {dir(request.app.state)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB client not available. Backend may not be fully initialized."
        )

    return mongo


# ==================== ROUTES ====================
@router.get(
    "/overview",
    response_model=StatsOverview,
    summary="Get statistics overview",
    tags=["stats"],
    responses={
        200: {"description": "Statistics retrieved successfully"},
        503: {"description": "MongoDB client unavailable"},
        500: {"description": "Internal server error"},
    }
)
async def get_stats_overview(
        request: Request,
        days: int = 30,
        form_type: Optional[str] = None
) -> StatsOverview:
    """
    Get aggregate statistics about processed forms.

    Query Parameters:
    - days: Number of days to look back (default: 30)
    - form_type: Filter by form type (ITF, NAR, or all)

    Returns:
        StatsOverview: Comprehensive statistics including processing counts,
        status breakdown, form types, and performance metrics.

    Raises:
        HTTPException: 503 if MongoDB not initialized
        HTTPException: 500 if statistics retrieval fails
    """
    logger.debug(f"📊 Fetching statistics for last {days} days, form_type={form_type}")

    try:
        # ✅ FIXED: Get MongoDB client using helper
        mongo_client = get_mongo_client(request)

        from config.settings import settings
        collection_name = settings.MONGODB_DB_COLLECTION

        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Build filter
        filters = {
            "timestamp": {"$gte": start_date, "$lte": end_date}
        }
        if form_type:
            filters["form_type"] = form_type.upper()

        logger.debug(f"📋 Applying filters: {filters}")

        # ==================== COUNT TOTAL PROCESSED ====================
        try:
            total_processed = await mongo_client.count_documents(
                collection_name,
                filters
            )
            logger.debug(f"✅ Total processed: {total_processed}")
        except Exception as e:
            logger.error(f"❌ Error counting documents: {e}", exc_info=True)
            raise

        # ==================== COUNT BY STATUS ====================
        try:
            status_pipeline = [
                {"$match": filters},
                {"$group": {
                    "_id": "$status",
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}}
            ]
            # ✅ FIXED: Use mongo_client.aggregate() which handles async properly
            status_results = await mongo_client.aggregate(
                collection_name,
                status_pipeline
            )
            status_counts = {item["_id"]: item["count"] for item in status_results}
            logger.debug(f"✅ Status breakdown: {status_counts}")
        except Exception as e:
            logger.error(f"❌ Error aggregating by status: {e}", exc_info=True)
            status_counts = {}

        # ==================== COUNT BY FORM TYPE ====================
        try:
            form_type_pipeline = [
                {"$match": filters},
                {"$group": {
                    "_id": "$form_type",
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}}
            ]
            # ✅ FIXED: Use mongo_client.aggregate() which handles async properly
            form_type_results = await mongo_client.aggregate(
                collection_name,
                form_type_pipeline
            )
            form_type_counts = {item["_id"]: item["count"] for item in form_type_results}
            logger.debug(f"✅ Form type breakdown: {form_type_counts}")
        except Exception as e:
            logger.error(f"❌ Error aggregating by form type: {e}", exc_info=True)
            form_type_counts = {}

        # ==================== PROCESSING TIME STATS ====================
        try:
            timing_pipeline = [
                {"$match": filters},
                {"$group": {
                    "_id": None,
                    "avg_processing_time": {"$avg": "$processing_time_ms"},
                    "max_processing_time": {"$max": "$processing_time_ms"},
                    "min_processing_time": {"$min": "$processing_time_ms"}
                }}
            ]
            # ✅ FIXED: Use mongo_client.aggregate() which handles async properly
            timing_results = await mongo_client.aggregate(
                collection_name,
                timing_pipeline
            )

            if timing_results and len(timing_results) > 0:
                timing_stats = timing_results[0]
                logger.debug(f"✅ Timing stats: avg={timing_stats.get('avg_processing_time')}")
            else:
                timing_stats = {
                    "avg_processing_time": 0,
                    "max_processing_time": 0,
                    "min_processing_time": 0
                }
        except Exception as e:
            logger.error(f"❌ Error calculating processing time: {e}", exc_info=True)
            timing_stats = {
                "avg_processing_time": 0,
                "max_processing_time": 0,
                "min_processing_time": 0
            }

        # ==================== CALCULATE SUCCESS RATE ====================
        completed_count = status_counts.get("completed", 0)
        success_rate = (
            round(completed_count / total_processed * 100, 2)
            if total_processed > 0
            else 0.0
        )

        # ==================== BUILD RESPONSE ====================
        response = StatsOverview(
            period_days=days,
            date_range={
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            total_processed=total_processed,
            by_status=status_counts,
            by_form_type=form_type_counts,
            processing_time_ms=ProcessingTimeStats(
                average=round(timing_stats.get("avg_processing_time", 0), 2),
                max=int(timing_stats.get("max_processing_time", 0) or 0),
                min=int(timing_stats.get("min_processing_time", 0) or 0)
            ),
            success_rate=success_rate
        )

        logger.debug(f"✅ Statistics compiled successfully")
        return response

    except HTTPException:
        # ✅ FIXED: Re-raise HTTPException so FastAPI handles it properly
        raise
    except Exception as e:
        logger.error(
            f"❌ Failed to fetch statistics: {type(e).__name__}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve statistics: {str(e)}"
        )


@router.get(
    "",
    summary="Stats endpoint info",
    tags=["stats"],
    responses={200: {"description": "Information about stats endpoints"}}
)
async def get_stats(request: Request) -> Dict[str, str]:
    """
    Basic stats endpoint information.

    Use /api/stats/overview for detailed statistics.
    """
    logger.debug("📊 Stats info requested")
    return {
        "message": "Use /api/stats/overview for detailed statistics",
        "endpoints": {
            "overview": "GET /api/stats/overview - Get comprehensive statistics",
        }
    }


# ==================== DEBUG ENDPOINT ====================
@router.get(
    "/debug/service-status",
    summary="Debug service status",
    tags=["debug"],
    responses={200: {"description": "Service initialization status"}}
)
async def debug_service_status(request: Request) -> Dict[str, Any]:
    """
    Debug endpoint to check service initialization.

    ⚠️ Only available in debug mode.
    """
    from config.settings import settings

    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debug endpoint not available in production"
        )

    app_state = request.app.state

    mongo_available = hasattr(app_state, 'mongo') and app_state.mongo is not None
    storage_available = hasattr(app_state, 'storage') and app_state.storage is not None

    return {
        "services_initialized": {
            "mongo": mongo_available,
            "storage": storage_available,
            "form_processor": hasattr(app_state, 'form_processor'),
            "minio": hasattr(app_state, 'minio'),
        },
        "available_attributes": [attr for attr in dir(app_state) if not attr.startswith('_')],
        "mongodb_status": "ready" if mongo_available else "not_initialized",
    }
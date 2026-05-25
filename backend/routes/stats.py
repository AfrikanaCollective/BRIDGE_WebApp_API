# backend/routes/stats.py

"""
Statistics and aggregate data routes.
"""

import logging
from fastapi import APIRouter, Request, HTTPException, status
from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, Any, List
from models.stats import ProcessingTimeStats, ProcessingTimeBreakdown, StatsOverviewExtended

logger = logging.getLogger(__name__)
router = APIRouter()


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


def _calculate_percentile(
        sorted_data: List[float],
        percentile: float,
) -> float:
    """
    Calculate percentile value from sorted data.

    Uses linear interpolation (nearest rank method).

    Args:
        sorted_data: Sorted list of numeric values
        percentile: Percentile to calculate (0-100)

    Returns:
        float: Percentile value rounded to 2 decimals
    """
    if not sorted_data:
        return 0.0

    n = len(sorted_data)

    # Handle edge cases
    if percentile <= 0:
        return round(sorted_data[0], 2)
    if percentile >= 100:
        return round(sorted_data[-1], 2)

    # Calculate index using linear interpolation
    # Formula: index = (percentile / 100) * (n - 1)
    index = (percentile / 100.0) * (n - 1)
    lower_index = int(index)
    upper_index = min(lower_index + 1, n - 1)

    # Linear interpolation between values
    if lower_index == upper_index:
        result = sorted_data[lower_index]
    else:
        fraction = index - lower_index
        result = (
                sorted_data[lower_index] * (1 - fraction) +
                sorted_data[upper_index] * fraction
        )

    return round(result, 2)


def _extract_processing_times(
        documents: List[Dict[str, Any]],
        time_key: str,
) -> List[float]:
    """
    Extract processing times from documents.

    Args:
        documents: List of MongoDB documents
        time_key: Metadata key to extract (e.g., 'processing_time_llm_seconds')

    Returns:
        List of processing times in seconds
    """
    times = []
    for doc in documents:
        metadata = doc.get("metadata", {})
        time_value = metadata.get(time_key)

        if time_value is not None and time_value > 0:
            times.append(float(time_value))

    return times


def _calculate_time_stats(
        times: List[float],
        stat_name: str = "Processing Time"
) -> Dict[str, float]:
    """
    Calculate percentile statistics for a list of times.

    Args:
        times: List of processing times in seconds
        stat_name: Name for logging purposes

    Returns:
        dict: {
            "median": float,
            "p25": float,
            "p975": float,
            "total_samples": int,
        }
    """
    if not times:
        logger.warning(f"⚠️  No {stat_name} data found")
        return {
            "median": 0.0,
            "p25": 0.0,
            "p975": 0.0,
            "total_samples": 0
        }

    sorted_times = sorted(times)
    n = len(sorted_times)

    # Calculate percentiles
    median = _calculate_percentile(sorted_times, 50)
    p25 = _calculate_percentile(sorted_times, 2.5)
    p975 = _calculate_percentile(sorted_times, 97.5)

    logger.info(
        f"⏱️  {stat_name} Statistics:\n"
        f"   Median (50th %ile): {median:.2f}s\n"
        f"   2.5th %ile: {p25:.2f}s\n"
        f"   97.5th %ile: {p975:.2f}s\n"
        f"   Samples: {n}\n"
        f"   Range: {sorted_times[0]:.2f}s - {sorted_times[-1]:.2f}s"
    )

    return {
        "median": median,
        "p25": p25,
        "p975": p975,
        "total_samples": n
    }


# ==================== ROUTES ====================
@router.get(
    "/overview",
    response_model=StatsOverviewExtended,
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
) -> StatsOverviewExtended:
    """
    Get aggregate statistics about processed forms.

    Query Parameters:
    - days: Number of days to look back (default: 30)
    - form_type: Filter by form type (ITF, NAR, or all)

    Returns:
        StatsOverviewExtended: Comprehensive statistics including processing counts,
        status breakdown, form types, and detailed processing time metrics broken
        down by LLM, Agent, and combined processing.

    Processing Time Breakdown:
    - llm_seconds: LLM-only processing time (text generation)
    - agent_seconds: Agent processing time (extraction + processing)
    - total_seconds: Combined LLM + Agent processing time

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
        end_date = datetime.now(UTC)
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
            form_type_results = await mongo_client.aggregate(
                collection_name,
                form_type_pipeline
            )
            form_type_counts = {item["_id"]: item["count"] for item in form_type_results}
            logger.debug(f"✅ Form type breakdown: {form_type_counts}")
        except Exception as e:
            logger.error(f"❌ Error aggregating by form type: {e}", exc_info=True)
            form_type_counts = {}

        # ==================== PROCESSING TIME STATS (LLM, AGENT, TOTAL) ====================
        llm_stats = {
            "median": 0.0,
            "p25": 0.0,
            "p975": 0.0,
            "total_samples": 0
        }
        agent_stats = {
            "median": 0.0,
            "p25": 0.0,
            "p975": 0.0,
            "total_samples": 0
        }
        total_stats = {
            "median": 0.0,
            "p25": 0.0,
            "p975": 0.0,
            "total_samples": 0
        }

        try:
            # Fetch all documents with processing time metadata
            timing_pipeline = [
                {"$match": filters},
                {
                    "$match": {
                        "$or": [
                            {"metadata.processing_time_llm_seconds": {"$exists": True, "$gt": 0}},
                            {"metadata.processing_time_agent_seconds": {"$exists": True, "$gt": 0}}
                        ]
                    }
                },
                {
                    "$project": {
                        "metadata.processing_time_llm_seconds": 1,
                        "metadata.processing_time_agent_seconds": 1,
                        "timestamp": 1
                    }
                }
            ]

            timing_documents = await mongo_client.aggregate(
                collection_name,
                timing_pipeline
            )

            logger.debug(f"📊 Collected {len(timing_documents)} documents with timing data")

            if timing_documents and len(timing_documents) > 0:
                # Extract separate time lists
                llm_times = _extract_processing_times(
                    timing_documents,
                    "processing_time_llm_seconds"
                )
                agent_times = _extract_processing_times(
                    timing_documents,
                    "processing_time_agent_seconds"
                )

                # Calculate total times (LLM + Agent)
                total_times = []
                for doc in timing_documents:
                    metadata = doc.get("metadata", {})
                    llm_val = metadata.get("processing_time_llm_seconds", 0)
                    agent_val = metadata.get("processing_time_agent_seconds", 0)
                    if llm_val > 0 and agent_val > 0:
                        total_times.append(float(llm_val + agent_val))

                logger.debug(
                    f"   LLM times: {len(llm_times)} samples\n"
                    f"   Agent times: {len(agent_times)} samples\n"
                    f"   Total times: {len(total_times)} samples"
                )

                # Calculate statistics for each component
                if llm_times:
                    llm_stats = _calculate_time_stats(llm_times, "LLM Processing Time (text generation only)")
                    logger.info(f"✅ LLM Stats - Samples: {llm_stats['total_samples']}")

                if agent_times:
                    agent_stats = _calculate_time_stats(agent_times, "Agent Processing Time (extraction + processing)")
                    logger.info(f"✅ Agent Stats - Samples: {agent_stats['total_samples']}")

                if total_times:
                    total_stats = _calculate_time_stats(total_times, "Total Processing Time (LLM + Agent)")
                    logger.info(f"✅ Total Stats - Samples: {total_stats['total_samples']}")

            else:
                logger.warning("⚠️  No processing time data found")

        except Exception as e:
            logger.error(f"❌ Error calculating processing time statistics: {e}", exc_info=True)

        # ==================== CALCULATE SUCCESS RATE ====================
        completed_count = status_counts.get("completed", 0)
        success_rate = (
            round(completed_count / total_processed * 100, 2)
            if total_processed > 0
            else 0.0
        )

        # ==================== BUILD RESPONSE ====================
        # Use total_stats for the main processing_time_ms field for backward compatibility
        response = StatsOverviewExtended(
            period_days=days,
            date_range={
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            total_processed=total_processed,
            by_status=status_counts,
            by_form_type=form_type_counts,
            processing_time_ms=ProcessingTimeStats(
                average=round(total_stats.get("median", 0) * 1000, 2),  # Convert to ms
                max=int(total_stats.get("p975", 0) * 1000),  # Convert to ms
                min=int(total_stats.get("p25", 0) * 1000)  # Convert to ms
            ),
            processing_time_breakdown=ProcessingTimeBreakdown(
                llm_seconds=ProcessingTimeStats(
                    average=round(llm_stats.get("median", 0), 2),
                    max=int(llm_stats.get("p975", 0)),
                    min=int(llm_stats.get("p25", 0))
                ),
                agent_seconds=ProcessingTimeStats(
                    average=round(agent_stats.get("median", 0), 2),
                    max=int(agent_stats.get("p975", 0)),
                    min=int(agent_stats.get("p25", 0))
                ),
                total_seconds=ProcessingTimeStats(
                    average=round(total_stats.get("median", 0), 2),
                    max=int(total_stats.get("p975", 0)),
                    min=int(total_stats.get("p25", 0))
                )
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
            "overview": "GET /api/stats/overview - Get comprehensive statistics with LLM/Agent/Total breakdown",
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

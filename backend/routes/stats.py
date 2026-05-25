# backend/routes/stats.py

"""
Statistics and aggregate data routes.
"""

import logging
from fastapi import APIRouter, Request, HTTPException, status
from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from models.stats import ProcessingTimeStats, StatsOverview

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


async def _calculate_processing_time_stats(
        db,
        collections: list,
) -> dict:
    """
    Calculate processing time statistics from MongoDB records.

    Aggregates process_time_llm and process_time_agent from metadata.
    Uses percentiles instead of min/max to reduce outlier impact.

    Returns:
        dict: {
            "median": float,           # 50th percentile
            "p25": float,              # 2.5th percentile
            "p975": float,             # 97.5th percentile
            "total_samples": int,
        }
    """
    all_processing_times: List[float] = []

    for collection_name in collections:
        if not collection_name.startswith("form_"):
            continue

        collection = db[collection_name]

        # ==================== AGGREGATE TIMING ====================
        # Pipeline to extract and sum LLM + Agent times
        pipeline = [
            {
                "$match": {
                    "metadata": {"$exists": True},
                    "$or": [
                        {"metadata.process_time_llm": {"$exists": True}},
                        {"metadata.process_time_agent": {"$exists": True}},
                    ]
                }
            },
            {
                "$project": {
                    "total_time": {
                        "$add": [
                            {
                                "$cond": [
                                    {"$ne": ["$metadata.process_time_llm", None]},
                                    "$metadata.process_time_llm",
                                    0
                                ]
                            },
                            {
                                "$cond": [
                                    {"$ne": ["$metadata.process_time_agent", None]},
                                    "$metadata.process_time_agent",
                                    0
                                ]
                            }
                        ]
                    }
                }
            },
            {
                "$match": {
                    "total_time": {"$gt": 0}  # Exclude zero times
                }
            },
            {
                "$sort": {"total_time": 1}  # Sort for percentile calculation
            }
        ]

        try:
            async for doc in collection.aggregate(pipeline):
                if doc.get("total_time") is not None:
                    all_processing_times.append(doc["total_time"])
                    logger.debug(
                        f"  {collection_name}: {doc['total_time']:.2f}s"
                    )
        except Exception as e:
            logger.warning(
                f"⚠️  Error aggregating times from {collection_name}: {e}"
            )
            continue

    logger.debug(f"📊 Collected {len(all_processing_times)} timing samples")

    # ==================== CALCULATE PERCENTILES ====================
    if not all_processing_times:
        logger.warning("⚠️  No processing time data found")
        return {
            "median": 0.0,
            "p25": 0.0,
            "p975": 0.0,
            "total_samples": 0,
        }

    # Sort for percentile calculation
    sorted_times = sorted(all_processing_times)
    n = len(sorted_times)

    # Calculate percentiles
    median = _calculate_percentile(sorted_times, 50)
    p25 = _calculate_percentile(sorted_times, 2.5)
    p975 = _calculate_percentile(sorted_times, 97.5)

    logger.info(
        f"⏱️  Processing Time Statistics:\n"
        f"   Median (50th %ile): {median}s\n"
        f"   2.5th %ile: {p25}s\n"
        f"   97.5th %ile: {p975}s\n"
        f"   Samples: {n}\n"
        f"   Range: {sorted_times[0]:.2f}s - {sorted_times[-1]:.2f}s"
    )

    return {
        "median": median,
        "p25": p25,
        "p975": p975,
        "total_samples": n,
    }


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

        # ==================== PROCESSING TIME STATS (PERCENTILE-BASED) ====================
        try:
            # Fetch all processing times with metadata
            timing_pipeline = [
                {"$match": filters},
                {
                    "$project": {
                        "total_time": {
                            "$add": [
                                {
                                    "$cond": [
                                        {"$ne": ["$metadata.process_time_llm", None]},
                                        "$metadata.process_time_llm",
                                        0
                                    ]
                                },
                                {
                                    "$cond": [
                                        {"$ne": ["$metadata.process_time_agent", None]},
                                        "$metadata.process_time_agent",
                                        0
                                    ]
                                }
                            ]
                        },
                        "processing_time_ms": 1
                    }
                },
                {
                    "$match": {
                        "$or": [
                            {"total_time": {"$gt": 0}},
                            {"processing_time_ms": {"$gt": 0}}
                        ]
                    }
                },
                {
                    "$sort": {
                        "total_time": 1
                    }
                }
            ]

            timing_results = await mongo_client.aggregate(
                collection_name,
                timing_pipeline
            )

            logger.debug(f"📊 Collected {len(timing_results)} timing samples")

            # Calculate percentiles from results
            if timing_results and len(timing_results) > 0:
                # Extract total_time values
                processing_times = [
                    doc.get("total_time", 0)
                    for doc in timing_results
                    if doc.get("total_time", 0) > 0
                ]

                if not processing_times:
                    # Fallback to processing_time_ms if available
                    processing_times = [
                        doc.get("processing_time_ms", 0) / 1000  # Convert ms to seconds
                        for doc in timing_results
                        if doc.get("processing_time_ms", 0) > 0
                    ]

                if processing_times:
                    sorted_times = sorted(processing_times)

                    # Calculate percentiles
                    median = _calculate_percentile(sorted_times, 50)
                    p25 = _calculate_percentile(sorted_times, 2.5)
                    p975 = _calculate_percentile(sorted_times, 97.5)

                    logger.info(
                        f"⏱️  Processing Time Statistics:\n"
                        f"   Median (50th %ile): {median}s\n"
                        f"   2.5th %ile: {p25}s\n"
                        f"   97.5th %ile: {p975}s\n"
                        f"   Samples: {len(sorted_times)}\n"
                        f"   Range: {sorted_times[0]:.2f}s - {sorted_times[-1]:.2f}s"
                    )

                    timing_stats = {
                        "median": median,
                        "p25": p25,
                        "p975": p975,
                        "total_samples": len(sorted_times)
                    }
                else:
                    logger.warning("⚠️  No valid processing times found")
                    timing_stats = {
                        "median": 0.0,
                        "p25": 0.0,
                        "p975": 0.0,
                        "total_samples": 0
                    }
            else:
                logger.warning("⚠️  No processing time data found")
                timing_stats = {
                    "median": 0.0,
                    "p25": 0.0,
                    "p975": 0.0,
                    "total_samples": 0
                }

        except Exception as e:
            logger.error(f"❌ Error calculating processing time percentiles: {e}", exc_info=True)
            timing_stats = {
                "median": 0.0,
                "p25": 0.0,
                "p975": 0.0,
                "total_samples": 0
            }

        # ==================== CALCULATE SUCCESS RATE ====================
        completed_count = status_counts.get("completed", 0)
        success_rate = (
            round(completed_count / total_processed * 100, 2)
            if total_processed > 0
            else 0.0
        )

        # ==================== BUILD RESPONSE ====================
        # Convert percentile times from seconds to milliseconds for response
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
                average=round(timing_stats.get("median", 0) * 1000, 2),  # Convert to ms
                max=int(timing_stats.get("p975", 0) * 1000),  # Convert to ms
                min=int(timing_stats.get("p25", 0) * 1000)  # Convert to ms
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
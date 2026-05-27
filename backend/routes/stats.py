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
def get_storage_service(request: Request):
    """
    ✅ FIXED: Consistent access to StorageService from app.state.

    This matches the pattern used in form_processor.py and ensures
    we're using the same initialized service throughout the app.

    Args:
        request: FastAPI request object

    Returns:
        StorageService instance

    Raises:
        HTTPException: 503 if storage service not initialized
    """
    storage = getattr(request.app.state, 'storage', None)

    if not storage:
        logger.error("❌ StorageService not initialized in app.state")
        logger.debug(f"Available app.state attributes: {dir(request.app.state)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="StorageService not available. Backend may not be fully initialized."
        )

    return storage


def get_mongo_client(request: Request):
    """
    ✅ FIXED: Get MongoClient via StorageService.

    Instead of accessing mongo directly, we get it through the
    initialized StorageService which guarantees consistency.

    Args:
        request: FastAPI request object

    Returns:
        MongoClient instance

    Raises:
        HTTPException: 503 if mongo client not available
    """
    storage = get_storage_service(request)

    # StorageService has mongo_client property
    mongo = storage.mongo

    if not mongo:
        logger.error("❌ MongoDB client not available via StorageService")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB client not available."
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

    ✅ FIXED: Extracts from TOP-LEVEL fields, not nested metadata.

    Args:
        documents: List of MongoDB documents
        time_key: Top-level field name to extract
                 (e.g., 'processing_time_llm_seconds')

    Returns:
        List of processing times in seconds (float)
    """
    times = []
    for doc in documents:
        # ✅ FIXED: Get from top-level field
        time_value = doc.get(time_key)

        if time_value is not None:
            try:
                time_float = float(time_value)
                if time_float > 0:
                    times.append(time_float)
            except (ValueError, TypeError) as e:
                logger.warning(f"⚠️  Could not convert {time_key}={time_value} to float: {e}")
                continue

    return times


def _calculate_time_stats(
        times: List[float],
        stat_name: str = "Processing Time"
) -> Dict[str, Any]:
    """
    Calculate statistics for a list of times.

    Args:
        times: List of processing times in seconds
        stat_name: Name for logging purposes

    Returns:
        dict: {
            "average": float,      # Simple arithmetic mean
            "median": float,       # 50th percentile
            "p25": float,          # 2.5th percentile (min)
            "p975": float,         # 97.5th percentile (max)
            "total_samples": int,
        }
    """
    if not times:
        logger.warning(f"⚠️  No {stat_name} data found")
        return {
            "average": 0.0,
            "median": 0.0,
            "p25": 0.0,
            "p975": 0.0,
            "total_samples": 0
        }

    sorted_times = sorted(times)
    n = len(sorted_times)

    # Calculate average
    average = sum(sorted_times) / n

    # Calculate percentiles
    median = _calculate_percentile(sorted_times, 50)
    p25 = _calculate_percentile(sorted_times, 2.5)
    p975 = _calculate_percentile(sorted_times, 97.5)

    logger.info(
        f"⏱️  {stat_name} Statistics:\n"
        f"   Average: {average:.2f}s\n"
        f"   Median (50th %ile): {median:.2f}s\n"
        f"   2.5th %ile: {p25:.2f}s\n"
        f"   97.5th %ile: {p975:.2f}s\n"
        f"   Samples: {n}\n"
        f"   Range: {sorted_times[0]:.2f}s - {sorted_times[-1]:.2f}s"
    )

    return {
        "average": round(average, 2),
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
        503: {"description": "StorageService/MongoDB unavailable"},
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

    Each component includes:
    - average: Arithmetic mean of processing times
    - max: 97.5th percentile (upper bound)
    - min: 2.5th percentile (lower bound)

    Raises:
        HTTPException: 503 if StorageService/MongoDB not initialized
        HTTPException: 500 if statistics retrieval fails
    """
    logger.info(f"📊 Fetching statistics for last {days} days, form_type={form_type}")

    try:
        # ✅ FIXED: Get MongoDB client via StorageService
        mongo_client = get_mongo_client(request)

        from config.settings import settings
        collection_name = settings.MONGODB_DB_COLLECTION

        # Calculate date range
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=days)

        # Build filter with proper timestamp handling
        filters = {
            "timestamp": {"$gte": start_date.isoformat(), "$lte": end_date.isoformat()}
        }
        if form_type:
            filters["form_type"] = form_type.upper()

        logger.debug(f"📋 Filter: {filters}")

        # ==================== COUNT TOTAL PROCESSED ====================
        try:
            total_processed = await mongo_client.count_documents(
                collection_name,
                filters
            )
            logger.info(f"✅ Total processed: {total_processed}")
        except Exception as e:
            logger.error(f"❌ Error counting documents: {e}", exc_info=True)
            total_processed = 0

        # ==================== COUNT BY STATUS ====================
        status_counts = {}
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
            logger.info(f"✅ Status breakdown: {status_counts}")
        except Exception as e:
            logger.error(f"❌ Error aggregating by status: {e}", exc_info=True)

        # ==================== COUNT BY FORM TYPE ====================
        form_type_counts = {}
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
            logger.info(f"✅ Form type breakdown: {form_type_counts}")
        except Exception as e:
            logger.error(f"❌ Error aggregating by form type: {e}", exc_info=True)

        # ==================== PROCESSING TIME STATS ====================
        llm_stats = {
            "average": 0.0,
            "median": 0.0,
            "p25": 0.0,
            "p975": 0.0,
            "total_samples": 0
        }
        agent_stats = {
            "average": 0.0,
            "median": 0.0,
            "p25": 0.0,
            "p975": 0.0,
            "total_samples": 0
        }
        total_stats = {
            "average": 0.0,
            "median": 0.0,
            "p25": 0.0,
            "p975": 0.0,
            "total_samples": 0
        }

        try:
            # ✅ FIXED: Fetch documents with TOP-LEVEL processing time fields
            timing_pipeline = [
                {"$match": filters},
                {
                    "$project": {
                        "_id": 1,
                        "processing_time_llm_seconds": 1,
                        "processing_time_agent_seconds": 1,
                        "timestamp": 1,
                        "status": 1
                    }
                }
            ]

            timing_documents = await mongo_client.aggregate(
                collection_name,
                timing_pipeline
            )

            logger.info(f"📊 Retrieved {len(timing_documents)} documents for timing analysis")

            if timing_documents and len(timing_documents) > 0:
                # ✅ FIXED: Extract from TOP-LEVEL fields
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
                    llm_val = doc.get("processing_time_llm_seconds", 0)
                    agent_val = doc.get("processing_time_agent_seconds", 0)

                    # Convert to float if needed
                    try:
                        llm_val = float(llm_val) if llm_val else 0
                        agent_val = float(agent_val) if agent_val else 0
                    except (ValueError, TypeError):
                        continue

                    if llm_val > 0 and agent_val > 0:
                        total_times.append(llm_val + agent_val)

                logger.info(
                    f"📊 Processing times extracted:\n"
                    f"   LLM samples: {len(llm_times)}\n"
                    f"   Agent samples: {len(agent_times)}\n"
                    f"   Total samples: {len(total_times)}"
                )

                # Calculate statistics for each component
                if llm_times:
                    llm_stats = _calculate_time_stats(llm_times, "LLM Processing")
                if agent_times:
                    agent_stats = _calculate_time_stats(agent_times, "Agent Processing")
                if total_times:
                    total_stats = _calculate_time_stats(total_times, "Total Processing")

            else:
                logger.warning("⚠️  No timing data found in query results")

        except Exception as e:
            logger.error(f"❌ Error calculating timing statistics: {e}", exc_info=True)

        # ==================== CALCULATE SUCCESS RATE ====================
        completed_count = status_counts.get("success", 0)
        success_rate = (
            round(completed_count / total_processed * 100, 2)
            if total_processed > 0
            else 0.0
        )

        logger.info(
            f"📈 Statistics Summary:\n"
            f"   Period: {days} days\n"
            f"   Total Processed: {total_processed}\n"
            f"   Success Rate: {success_rate}%\n"
            f"   Status: {status_counts}\n"
            f"   Form Types: {form_type_counts}\n"
            f"   LLM Times (samples={llm_stats['total_samples']}): median={llm_stats['median']}s\n"
            f"   Agent Times (samples={agent_stats['total_samples']}): median={agent_stats['median']}s\n"
            f"   Total Times (samples={total_stats['total_samples']}): median={total_stats['median']}s"
        )

        # ✅ NEW: Get active users
        active_users = 0
        try:
            session_service = getattr(request.app.state, 'session_service', None)
            if session_service:
                active_sessions = session_service.get_ip_address_stats()["unique_ip_count"]
                logger.info(f"✅ Active sessions: {active_sessions}")
        except Exception as e:
            logger.warning(f"⚠️  Could not retrieve active sessions: {e}")

        # ==================== BUILD RESPONSE ====================
        response = StatsOverviewExtended(
            period_days=days,
            date_range={
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            total_processed=total_processed,
            by_status=status_counts,
            by_form_type=form_type_counts,
            processing_time_breakdown=ProcessingTimeBreakdown(
                llm_seconds=ProcessingTimeStats(
                    average=llm_stats.get("median", 0.0),
                    max=int(llm_stats.get("p975", 0)),
                    min=int(llm_stats.get("p25", 0))
                ),
                agent_seconds=ProcessingTimeStats(
                    average=agent_stats.get("median", 0.0),
                    max=int(agent_stats.get("p975", 0)),
                    min=int(agent_stats.get("p25", 0))
                ),
                total_seconds=ProcessingTimeStats(
                    average=total_stats.get("median", 0.0),
                    max=int(total_stats.get("p975", 0)),
                    min=int(total_stats.get("p25", 0))
                )
            ),
            success_rate=success_rate,
            active_sessions=active_sessions
        )

        logger.debug(f"✅ Statistics response compiled")
        return response

    except HTTPException:
        # Re-raise HTTPException so FastAPI handles it properly
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
async def get_stats_info(request: Request) -> Dict[str, Any]:
    """
    Basic stats endpoint information.

    Use /api/stats/overview for detailed statistics.
    """
    logger.debug("📊 Stats info requested")
    return {
        "message": "Use /api/stats/overview for detailed statistics",
        "endpoints": {
            "overview": "GET /api/stats/overview - Get comprehensive statistics with LLM/Agent/Total breakdown"
        }
    }


# ==================== DEBUG ENDPOINT ====================
@router.get(
    "/debug/service-status",
    summary="Debug: Service initialization status",
    tags=["debug"],
    responses={200: {"description": "Service initialization status"}}
)
async def debug_service_status(request: Request) -> Dict[str, Any]:
    """
    Debug endpoint to check service initialization.

    ⚠️ Only available in debug mode.

    Returns:
        - services_initialized: Status of each service
        - app_state_attributes: All non-private attributes in app.state
        - storage_service_info: Details about StorageService initialization
    """
    from config.settings import settings

    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debug endpoint not available in production"
        )

    app_state = request.app.state

    # Check service availability
    storage = getattr(app_state, 'storage', None)
    mongo = getattr(app_state, 'mongo', None)

    storage_available = storage is not None
    mongo_available = mongo is not None

    return {
        "services_initialized": {
            "storage": storage_available,
            "mongo": mongo_available,
            "form_processor": hasattr(app_state, 'form_processor'),
            "minio": hasattr(app_state, 'minio'),
        },
        "app_state_attributes": [attr for attr in dir(app_state) if not attr.startswith('_')],
        "storage_service_info": {
            "initialized": storage_available,
            "has_mongo": storage.mongo is not None if storage_available else False,
            "collection": storage.collection_name if storage_available else None,
            "db": storage.db_name if storage_available else None,
        },
        "mongodb_status": "ready" if mongo_available else "not_initialized",
    }


@router.get(
    "/debug/documents",
    summary="Debug: Sample documents from MongoDB",
    tags=["debug"],
    responses={200: {"description": "Sample documents and metadata"}}
)
async def debug_documents(request: Request, limit: int = 5) -> Dict[str, Any]:
    """
    Debug endpoint to inspect documents in MongoDB.

    ⚠️ Only available in debug mode.

    Query Parameters:
    - limit: Number of sample documents to retrieve (default: 5)

    Returns:
        - total_documents: Total count in collection
        - documents_last_30_days: Count in 30-day window
        - documents_last_365_days: Count in 365-day window
        - sample_documents: Sample documents with key fields
        - field_analysis: Analysis of timestamp and field formats
    """
    from config.settings import settings

    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debug endpoint not available in production"
        )

    try:
        mongo_client = get_mongo_client(request)
        collection_name = settings.MONGODB_DB_COLLECTION

        # Get total count
        total_count = await mongo_client.count_documents(collection_name, {})

        # Get date ranges
        end_date = datetime.now(UTC)
        start_date_30 = end_date - timedelta(days=30)
        start_date_365 = end_date - timedelta(days=365)

        # Count by date ranges
        count_30_days = await mongo_client.count_documents(
            collection_name,
            {
                "timestamp": {
                    "$gte": start_date_30.isoformat(),
                    "$lte": end_date.isoformat()
                }
            }
        )

        count_365_days = await mongo_client.count_documents(
            collection_name,
            {
                "timestamp": {
                    "$gte": start_date_365.isoformat(),
                    "$lte": end_date.isoformat()
                }
            }
        )

        # Get sample documents
        pipeline = [
            {"$limit": limit},
            {
                "$project": {
                    "_id": 1,
                    "timestamp": 1,
                    "form_type": 1,
                    "status": 1,
                    "processing_time_llm_seconds": 1,
                    "processing_time_agent_seconds": 1,
                    "created_at": 1,
                }
            }
        ]

        samples = await mongo_client.aggregate(collection_name, pipeline)

        return {
            "total_documents": total_count,
            "date_range_analysis": {
                "last_30_days": count_30_days,
                "last_365_days": count_365_days,
                "range_start": start_date_30.isoformat(),
                "range_end": end_date.isoformat(),
            },
            "sample_documents": samples,
            "debug_note": (
                f"If documents_last_30_days is 0, documents may be outside the 30-day window. "
                f"Total documents: {total_count}. Try querying with ?days=365"
            )
        }

    except Exception as e:
        logger.error(f"❌ Debug error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Debug error: {str(e)}"
        )

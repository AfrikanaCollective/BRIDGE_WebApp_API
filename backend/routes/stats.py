from fastapi import APIRouter, Request, HTTPException
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/overview")
async def get_stats_overview(
        request: Request,
        days: int = 30,
        form_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get aggregate statistics about processed forms.

    Query Parameters:
    - days: Number of days to look back (default: 30)
    - form_type: Filter by form type (ITF, NAR, or all)
    """
    try:
        # Get MongoDB client from app state
        mongo_client = getattr(request.app.state, 'mongo_client', None)
        if not mongo_client:
            raise HTTPException(
                status_code=503,
                detail="MongoDB client not available"
            )

        db = mongo_client.db
        forms_collection = db.get_collection('forms')

        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Build filter
        filters = {
            "timestamp": {"$gte": start_date, "$lte": end_date}
        }
        if form_type:
            filters["form_type"] = form_type.upper()

        # Aggregate statistics
        total_processed = await forms_collection.count_documents(filters)

        # Count by status
        status_pipeline = [
            {"$match": filters},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        status_results = await forms_collection.aggregate(status_pipeline).to_list(None)
        status_counts = {item["_id"]: item["count"] for item in status_results}

        # Count by form_type
        form_type_pipeline = [
            {"$match": filters},
            {"$group": {
                "_id": "$form_type",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        form_type_results = await forms_collection.aggregate(form_type_pipeline).to_list(None)
        form_type_counts = {item["_id"]: item["count"] for item in form_type_results}

        # Average processing time
        timing_pipeline = [
            {"$match": filters},
            {"$group": {
                "_id": None,
                "avg_processing_time": {"$avg": "$processing_time_ms"},
                "max_processing_time": {"$max": "$processing_time_ms"},
                "min_processing_time": {"$min": "$processing_time_ms"}
            }}
        ]
        timing_results = await forms_collection.aggregate(timing_pipeline).to_list(None)
        timing_stats = timing_results[0] if timing_results else {
            "avg_processing_time": 0,
            "max_processing_time": 0,
            "min_processing_time": 0
        }

        return {
            "period_days": days,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "total_processed": total_processed,
            "by_status": status_counts,
            "by_form_type": form_type_counts,
            "processing_time_ms": {
                "average": round(timing_stats.get("avg_processing_time", 0), 2),
                "max": timing_stats.get("max_processing_time", 0),
                "min": timing_stats.get("min_processing_time", 0)
            },
            "success_rate": round(
                (status_counts.get("completed", 0) / total_processed * 100)
                if total_processed > 0 else 0,
                2
            )
        }

    except Exception as e:
        logger.error(f"Stats overview error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve statistics: {str(e)}"
        )


@router.get("")
async def get_stats(request: Request) -> Dict[str, str]:
    """Basic stats endpoint."""
    return {"message": "Use /api/stats/overview for detailed statistics"}

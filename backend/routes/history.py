# backend/routes/history.py

"""
History and record management route.
Provides paginated access to form processing records with filtering,
statistics, and deletion capabilities.

"""

import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, status, Path, Query

from models.history import (
    FormRecord,
    HistoryResponse,
    HistoryStats,
    RecordResponse,
    DeleteResponse
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== HELPER FUNCTIONS ====================
def get_storage_service(request: Request):
    """
    ✅ FIXED: Validate storage service with better error messages.
    """
    storage_service = getattr(request.app.state, 'storage', None)

    if not storage_service:
        logger.error("❌ Storage service not initialized in app.state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service not available. Backend may not be fully initialized."
        )

    return storage_service


# ==================== ROUTES ====================
# ✅ FIXED: Base history endpoint (no path parameters)
@router.get(
    "/",
    response_model=HistoryResponse,
    summary="Get form processing history",
    tags=["history"]
)
async def get_history(
        request: Request,
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        limit: int = Query(20, ge=1, le=100, description="Records per page"),
        form_type: Optional[str] = Query(None, description="Filter by form type (ITF, NAR)"),
        status_filter: Optional[str] = Query(None, description="Filter by status (pending, completed, failed)"),
) -> HistoryResponse:
    """
    Retrieve paginated form processing history.

    Supports filtering by form_type and status. Default ordering is by
    creation date (most recent first).
    """
    logger.debug(f"📜 Fetching history: page={page}, limit={limit}, form_type={form_type}, status={status_filter}")

    try:
        storage_service = get_storage_service(request)

        filters = {}
        if form_type:
            filters["form_type"] = form_type.upper()
        if status_filter:
            filters["status"] = status_filter.lower()

        logger.debug(f"Applying filters: {filters}")

        result = await storage_service.get_records(
            page=page,
            limit=limit,
            filters=filters,
        )

        # ✅ FIXED: Handle null case_id and other optional fields gracefully
        records = []
        for rec in result.get("records", []):
            try:
                record_dict = storage_service.record_to_dict(rec)
                # Ensure _id is present
                if "_id" in record_dict:
                    record_dict["id"] = str(record_dict.pop("_id"))
                elif "_id" in rec:
                    record_dict["id"] = str(rec["_id"])

                form_record = FormRecord(**record_dict)
                records.append(form_record)
            except Exception as e:
                logger.warning(f"⚠️  Failed to parse record {rec.get('_id')}: {e}")
                continue

        # ✅ FIXED: Match HistoryResponse field names
        response = HistoryResponse(
            total_count=result.get("total", 0),
            page=page,
            page_size=limit,
            total_pages=(result.get("total", 0) + limit - 1) // limit if limit > 0 else 0,
            records=records,
        )

        logger.debug(f"✅ Retrieved {len(records)} records")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to fetch history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch history: {str(e)}"
        )


# ✅ FIXED: Stats route BEFORE parameterized route
@router.get(
    "/stats/overview",
    response_model=HistoryStats,
    summary="Get statistics overview",
    tags=["history"]
)
async def get_stats_overview(request: Request) -> HistoryStats:
    """
    Retrieve aggregate statistics across all records.
    Includes counts by status and form type, plus overall success rate.
    """
    logger.debug("📊 Fetching statistics overview")

    try:
        storage_service = get_storage_service(request)

        stats = await storage_service.get_statistics()

        # ✅ FIXED: Build response using HistoryStats model fields
        response = HistoryStats(
            total_processed=stats.get("total", 0),
            by_status={
                "success": stats.get("success", 0),
                "failed": stats.get("failed", 0),
                "pending": stats.get("pending", 0),
            },
            by_form_type=stats.get("by_form_type", {}),
            success_rate=stats.get("success_rate", 0.0),
        )

        logger.debug(f"✅ Retrieved statistics: {response}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to fetch statistics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch statistics: {str(e)}"
        )


# ✅ FIXED: Parameterized routes AFTER specific routes
@router.get(
    "/{processing_id}",
    response_model=RecordResponse,
    summary="Get single record by processing_id",
    tags=["history"]
)
async def get_record(
        request: Request,
        processing_id: str = Path(..., description="Unique processing identifier"),
) -> RecordResponse:
    """
    Retrieve a single form processing record by processing_id.
    """
    logger.debug(f"🔍 Fetching record: {processing_id}")

    try:
        storage_service = get_storage_service(request)
        record = await storage_service.get_record_by_processing_id(processing_id)

        if not record:
            logger.warning(f"⚠️  Record not found: {processing_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Record not found: {processing_id}"
            )

        # ✅ FIXED: Handle record conversion with null fields gracefully
        try:
            record_dict = storage_service.record_to_dict(record)
            if "_id" in record_dict:
                record_dict["id"] = str(record_dict.pop("_id"))
            elif "_id" in record:
                record_dict["id"] = str(record.get("_id", ""))

            form_record = FormRecord(**record_dict)
        except Exception as e:
            logger.error(f"❌ Failed to parse record {processing_id}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to parse record data: {str(e)}"
            )

        response = RecordResponse(
            record=form_record,
            file_url=record.get("file_url"),
        )

        logger.debug(f"✅ Retrieved record: {processing_id}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to fetch record {processing_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch record: {str(e)}"
        )


@router.delete(
    "/{processing_id}",
    response_model=DeleteResponse,
    summary="Delete a record and associated files",
    tags=["history"]
)
async def delete_record(
        request: Request,
        processing_id: str = Path(..., description="Unique processing identifier"),
) -> DeleteResponse:
    """
    Delete a form processing record and associated MinIO files.
    """
    logger.debug(f"🗑️  Deleting record: {processing_id}")

    try:
        storage_service = get_storage_service(request)

        record = await storage_service.get_record_by_processing_id(processing_id)

        if not record:
            logger.warning(f"⚠️  Record not found for deletion: {processing_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Record not found: {processing_id}"
            )

        success = await storage_service.delete_record(processing_id)

        if not success:
            logger.warning(f"⚠️  Deletion failed for: {processing_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete record"
            )

        logger.info(f"✅ Record deleted: {processing_id}")

        return DeleteResponse(
            deleted=True,
            processing_id=processing_id,
            message="Record and associated files deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete record {processing_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete record: {str(e)}"
        )
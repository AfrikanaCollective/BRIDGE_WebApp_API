# backend/routes/history.py
"""
History and record management route.
Provides paginated access to form processing records with filtering,
statistics, and deletion capabilities.
"""

import json
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
# ✅ FIXED: Stats route BEFORE parameterized route (avoid path conflicts)
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
                "success": stats.get("completed", 0),  # Map 'completed' → 'success'
                "failed": stats.get("failed", 0),
                "pending": stats.get("pending", 0),
            },
            by_form_type=stats.get("by_form_type", {}),
            success_rate=stats.get("completion_rate", 0.0),
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
        status_filter: Optional[str] = Query(None, description="Filter by status (pending, success, failed)"),
) -> HistoryResponse:
    """
    Retrieve paginated form processing history.

    Supports filtering by form_type and status. Default ordering is by
    creation date (most recent first).

    Query Parameters:
    - page: Page number starting from 1
    - limit: Records per page (max 100)
    - form_type: Optional filter (ITF, NAR, etc.)
    - status_filter: Optional filter (pending, success, failed)
    """
    logger.debug(
        f"📜 Fetching history: page={page}, limit={limit}, "
        f"form_type={form_type}, status={status_filter}"
    )

    try:
        storage_service = get_storage_service(request)

        # ✅ Build filters dict
        filters = {}
        if form_type:
            filters["form_type"] = form_type.upper()
        if status_filter:
            filters["status"] = status_filter.lower()

        logger.debug(f"Applying filters: {filters}")

        # ✅ Call storage service to get pre-mapped records
        result = await storage_service.get_records(
            page=page,
            limit=limit,
            filters=filters,
        )

        raw_records = result.get("records", [])
        logger.debug(f"📦 Retrieved {len(raw_records)} records from storage service")

        # ✅ Log first raw record for diagnostic
        if raw_records:
            logger.info(
                f"🔍 RAW MONGODB RECORD (first): "
                f"{json.dumps(raw_records[0], default=str, indent=2)}"
            )

        # ✅ SIMPLIFIED: Records are already mapped from storage_service.get_records()
        # No need to call record_to_dict() again
        records = []
        for mapped_record in raw_records:
            try:
                logger.debug(
                    f"📦 Processing mapped record: "
                    f"{json.dumps(mapped_record, default=str, indent=2)}"
                )

                # ✅ Create FormRecord directly from pre-mapped data
                form_record = FormRecord(**mapped_record)
                logger.debug(
                    f"✅ FormRecord created: id={form_record.id}, "
                    f"processingId={form_record.processingId}"
                )

                records.append(form_record)

            except Exception as e:
                logger.warning(
                    f"⚠️  Failed to create FormRecord from mapped data: {e}",
                    exc_info=True
                )
                continue

        # ✅ Build response with correct field names
        response = HistoryResponse(
            total_count=result.get("total", 0),
            page=page,
            page_size=limit,
            total_pages=(result.get("total", 0) + limit - 1) // limit if limit > 0 else 0,
            records=records,
        )

        logger.debug(
            f"✅ Retrieved {len(records)} records successfully "
            f"(total: {response.total_count}, pages: {response.total_pages})"
        )
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to fetch history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch history: {str(e)}"
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

    Returns complete record details including all field mappings
    and associated file URLs.
    """
    logger.debug(f"🔍 Fetching record: {processing_id}")

    try:
        storage_service = get_storage_service(request)

        # ✅ get_record_by_processing_id() already returns fully mapped data
        mapped_record = await storage_service.get_record_by_processing_id(processing_id)

        if not mapped_record:
            logger.warning(f"⚠️  Record not found: {processing_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Record not found: {processing_id}"
            )

        # ✅ Log mapped data for diagnostic
        logger.debug(
            f"📦 Mapped record data: "
            f"{json.dumps(mapped_record, default=str, indent=2)}"
        )

        # ✅ SIMPLIFIED: Create FormRecord directly from pre-mapped data
        try:
            form_record = FormRecord(**mapped_record)
            logger.debug(
                f"✅ FormRecord created: id={form_record.id}, "
                f"processingId={form_record.processingId}"
            )

        except Exception as e:
            logger.error(
                f"❌ Failed to create FormRecord for {processing_id}: {e}",
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to parse record data: {str(e)}"
            )

        # ✅ Build response with fileUrl from mapped data
        response = RecordResponse(
            record=form_record,
            file_url=mapped_record.get("fileUrl"),  # Use camelCase key
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


# ✅ DELETE endpoint for record deletion
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

    Removes the MongoDB document and cleans up any associated
    S3/MinIO objects (images, JSON results).
    """
    logger.debug(f"🗑️  Deleting record: {processing_id}")

    try:
        storage_service = get_storage_service(request)

        # ✅ Verify record exists before deletion
        record = await storage_service.get_record_by_processing_id(processing_id)

        if not record:
            logger.warning(f"⚠️  Record not found for deletion: {processing_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Record not found: {processing_id}"
            )

        # ✅ Perform deletion
        success = await storage_service.delete_record(processing_id)

        if not success:
            logger.warning(f"⚠️  Deletion failed for: {processing_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete record"
            )

        logger.info(f"✅ Record deleted successfully: {processing_id}")

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

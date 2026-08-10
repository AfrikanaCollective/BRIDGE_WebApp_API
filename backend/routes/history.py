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

from utils.patient_id import extract_patient_id

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
# Stats route BEFORE parameterized route (avoid path conflicts)
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

        # ✅ FIXED: Build response using HistoryStats model fields (camelCase)
        response = HistoryStats(
            totalProcessed=stats.get("total", 0),
            byStatus={
                "success": stats.get("completed", 0),  # Map 'completed' → 'success'
                "failed": stats.get("failed", 0),
            },
            byFormType=stats.get("by_form_type", {}),
            successRate=stats.get("completion_rate", 0.0),
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


# Base history endpoint (no path parameters)
@router.get(
    "",  # Handle both cases,
    response_model=HistoryResponse,
    summary="Get form processing history",
    tags=["history"]
)
@router.get(
    "/",  # Handle both cases,
    response_model=HistoryResponse,
    summary="Get form processing history",
    tags=["history"]
)
async def get_history(
        request: Request,
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        limit: int = Query(100, ge=1, le=500, description="Records per page"),
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
                f"🔍 RAW MAPPED RECORD (first): "
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

        # ✅ Calculate pagination
        total = result.get("total", 0)
        total_pages = (total + limit - 1) // limit if limit > 0 else 0

        logger.debug(
            f"Pagination: total={total}, page={page}, limit={limit}, pages={total_pages}"
        )

        response = HistoryResponse(
            totalCount=total,
            page=page,
            pageSize=limit,
            totalPages=total_pages,
            records=records,
        )

        logger.debug(
            f"✅ Retrieved {len(records)} records successfully "
            f"(total: {response.totalCount}, pages: {response.totalPages})"
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
            fileUrl=mapped_record.get("fileUrl"),  # Use camelCase key
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
    "/{record_id}",
    response_model=DeleteResponse,
    summary="Delete a record and associated files",
    tags=["history"],
    responses={
        200: {
            "description": "Record deleted successfully",
            "content": {
                "application/json": {
                    "example": {
                        "deleted": True,
                        "processingId": "6a1536949d9200e023e07679",
                        "message": "Record and associated files deleted successfully (strategy: ObjectId(_id), cleaned up 2 files)"
                    }
                }
            }
        },
        404: {
            "description": "Record not found",
            "content": {
                "application/json": {
                    "example": {
                        "deleted": False,
                        "processingId": "invalid_id",
                        "message": "Record not found: invalid_id (tried: ObjectId(_id), string _id, processing_id field)"
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "deleted": False,
                        "processingId": "6a1536949d9200e023e07679",
                        "message": "Failed to delete record: Database connection error"
                    }
                }
            }
        }
    }
)
async def delete_record(
        request: Request,
        record_id: str = Path(
            ...,
            description="Unique record identifier (MongoDB _id or processing_id)",
            example="6a1536949d9200e023e07679"
        ),
) -> DeleteResponse:
    """
    Delete a form processing record and associated MinIO files.

    This endpoint removes:
    - The MongoDB document
    - Associated S3/MinIO objects (original image, result JSON)

    **Query Strategies (auto-attempted in order):**
    1. ObjectId lookup on `_id` field
    2. String lookup on `_id` field
    3. Lookup on `processing_id` field

    **Parameters:**
    - `record_id`: Can be either the MongoDB `_id` (as string or ObjectId)
                   or the `processing_id` field value

    **Example requests:**
    ```
    DELETE /api/history/6a1536949d9200e023e07679
    DELETE /api/history/processing_id_value
    ```

    **Response includes:**
    - `deleted`: Boolean status of deletion
    - `processingId`: Processing ID of deleted record
    - `message`: Detailed message including query strategy used and cleanup summary
    """
    logger.info(f"🔍 DELETE REQUEST: record_id={record_id}")

    # ================================================================
    # Input validation
    # ================================================================
    if not record_id or not record_id.strip():
        logger.warning("⚠️  Empty record_id provided")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="record_id cannot be empty"
        )

    try:
        # ============================================================
        # Get storage service instance
        # ============================================================
        storage_service = get_storage_service(request)
        logger.debug(f"✅ StorageService initialized for deletion")

        # ============================================================
        # Call delete_record with triple-lookup strategy
        # Returns detailed dict with success/failure info
        # ============================================================
        logger.debug(f"📋 Calling storage_service.delete_record('{record_id}')")
        deletion_result = await storage_service.delete_record(record_id)

        # ============================================================
        # Extract result details
        # ============================================================
        success = deletion_result.get("success", False)
        processing_id = deletion_result.get("processing_id", record_id)
        query_strategy = deletion_result.get("query_strategy", "unknown")
        cleanup_results = deletion_result.get("cleanup_results", [])
        strategies_tried = deletion_result.get("strategies_tried", [])

        # ================================================================
        # Handle deletion failure (record not found)
        # ================================================================
        if not success:
            strategies_str = ", ".join(strategies_tried) if strategies_tried else "unknown"
            message = f"Record not found: {record_id} (tried: {strategies_str})"

            logger.warning(
                f"⚠️  Record deletion failed: {message}"
            )

            return DeleteResponse(
                deleted=False,
                processing_id=processing_id,
                message=message
            )

        # ================================================================
        # Cascade delete → patient_summary (patient_summary_viz is then
        # handled automatically by VizStreamWatcher's delete event handler)
        # ================================================================
        image_filename = deletion_result.get("image_filename")
        patient_id = extract_patient_id(image_filename) if image_filename else None
        if patient_id:
            patient_summary_svc = getattr(
                request.app.state, "patient_summary_service", None
            )
            if patient_summary_svc:
                try:
                    await patient_summary_svc.delete_by_patient_id(patient_id)
                except Exception as e:
                    logger.error(
                        f"⚠️  patient_summary cascade delete failed for "
                        f"patient_id={patient_id!r}: {e}",
                        exc_info=True,
                    )
            else:
                logger.warning(
                    "⚠️  patient_summary_service not in app.state — "
                    "patient_summary row not removed"
                )
        else:
            logger.warning(
                f"⚠️  Could not extract patient_id from image_filename="
                f"{image_filename!r}; patient_summary row not removed"
            )

        # ================================================================
        # Build success response
        # ================================================================
        cleanup_count = len(cleanup_results)
        cleanup_deleted = sum(1 for c in cleanup_results if c.get("deleted"))

        cleanup_summary = (
            f"cleaned up {cleanup_deleted}/{cleanup_count} files"
            if cleanup_count > 0
            else "no associated files to clean up"
        )

        message = (
            f"Record and associated files deleted successfully "
            f"(strategy: {query_strategy}, {cleanup_summary})"
        )

        logger.info(
            f"✅ Record deletion successful: "
            f"processing_id={processing_id}, {cleanup_summary}"
        )

        logger.debug(f"📤 Returning success response for {processing_id}")

        return DeleteResponse(
            deleted=True,
            processing_id=processing_id,
            message=message
        )

    # ================================================================
    # Handle HTTPException (from above)
    # ================================================================
    except HTTPException as http_exc:
        logger.warning(f"⚠️  HTTPException raised: {http_exc.detail}")
        raise http_exc

    # ================================================================
    # Handle unexpected exceptions
    # ================================================================
    except Exception as e:
        error_msg = f"Failed to delete record: {str(e)}"
        logger.error(
            f"❌ Unexpected error during deletion of {record_id}: {error_msg}",
            exc_info=True
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=DeleteResponse(
                deleted=False,
                processing_id=record_id,
                message=error_msg
            ).model_dump(by_alias=True)
        )

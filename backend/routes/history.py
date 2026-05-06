# backend/app/routes/history.py
"""
History and record management route.
Provides paginated access to form processing records with filtering,
statistics, and deletion capabilities.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, status, Path, Query
from pydantic import BaseModel, Field

from config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== RESPONSE MODELS ====================
class FormRecord(BaseModel):
    """Individual form processing record."""
    _id: str = Field(..., description="MongoDB ObjectId")
    processing_id: str = Field(..., description="Unique processing identifier")
    form_type: str = Field(..., description="Type of form (ITF, NAR)")
    case_id: str = Field(..., description="Associated case identifier")
    status: str = Field(..., description="Processing status (pending, completed, failed)")
    confidence: Optional[float] = Field(None, description="Extraction confidence score")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    updated_at: str = Field(..., description="Last update timestamp (ISO 8601)")
    file_url: Optional[str] = Field(None, description="MinIO file URL")
    error_message: Optional[str] = Field(None, description="Error details if failed")
    extracted_data: Optional[dict] = Field(None, description="Extracted form data")


class HistoryResponse(BaseModel):
    """Paginated history response."""
    total: int = Field(..., description="Total number of records")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Records per page")
    records: list[FormRecord] = Field(..., description="Form records for this page")


class StatsOverview(BaseModel):
    """Aggregate statistics overview."""
    total: int = Field(..., description="Total records processed")
    completed: int = Field(..., description="Successfully completed records")
    failed: int = Field(..., description="Failed processing records")
    pending: int = Field(..., description="Pending/in-progress records")
    average_confidence: Optional[float] = Field(
        None, description="Average confidence score (completed records)"
    )
    completion_rate: float = Field(..., description="Percentage of completed records")


class RecordResponse(BaseModel):
    """Single record response."""
    record: FormRecord = Field(..., description="Form record details")
    file_url: Optional[str] = Field(None, description="Associated file URL")


class DeleteResponse(BaseModel):
    """Deletion confirmation response."""
    deleted: bool = Field(..., description="Deletion success status")
    processing_id: str = Field(..., description="Deleted processing identifier")
    message: str = Field(..., description="Deletion details")


# ==================== HELPER FUNCTIONS ====================
def record_to_dict(record: dict) -> dict:
    """Convert MongoDB record to response dictionary."""
    if record is None:
        return None

    return {
        "_id": str(record.get("_id", "")),
        "processing_id": record.get("processing_id", ""),
        "form_type": record.get("form_type", ""),
        "case_id": record.get("case_id", ""),
        "status": record.get("status", ""),
        "confidence": record.get("confidence"),
        "created_at": record.get("created_at", ""),
        "updated_at": record.get("updated_at", ""),
        "file_url": record.get("file_url"),
        "error_message": record.get("error_message"),
        "extracted_data": record.get("extracted_data"),
    }


async def get_record_by_processing_id(
        storage_service,
        processing_id: str,
) -> Optional[dict]:
    """
    Retrieve a single record by processing_id.

    Args:
        storage_service: StorageService instance
        processing_id: Unique processing identifier

    Returns:
        Record dictionary or None
    """
    try:
        record = await storage_service.get_record_by_processing_id(processing_id)
        return record_to_dict(record)
    except Exception as e:
        logger.error(f"❌ Failed to fetch record {processing_id}: {e}")
        raise


# ==================== ROUTES ====================
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

    **Query Parameters:**
    - page: Page number (default 1, minimum 1)
    - limit: Records per page (default 20, maximum 100)
    - form_type: Filter by form type (ITF, NAR)
    - status_filter: Filter by status (pending, completed, failed)

    **Response:**
    - total: Total number of matching records
    - page: Current page number
    - limit: Records per page
    - records: Array of form records

    **Example:**
    ```bash
    # Get first page (20 records)
    curl http://localhost:6000/api/history/

    # Get page 2 with 50 records per page
    curl "http://localhost:6000/api/history/?page=2&limit=50"

    # Filter by form type
    curl "http://localhost:6000/api/history/?form_type=ITF"

    # Filter by status
    curl "http://localhost:6000/api/history/?status_filter=completed"
    ```
    """
    logger.debug(f"📜 Fetching history: page={page}, limit={limit}")

    try:
        # ✅ CHANGE 1: Access storage from app.state
        storage_service = request.app.state.storage

        if not storage_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storage service not available"
            )

        # Build filter
        filters = {}
        if form_type:
            filters["form_type"] = form_type.upper()
        if status_filter:
            filters["status"] = status_filter.lower()

        logger.debug(f"Applying filters: {filters}")

        # Fetch records
        result = await storage_service.get_records(
            page=page,
            limit=limit,
            filters=filters,
        )

        records = [
            FormRecord(**record_to_dict(rec))
            for rec in result.get("records", [])
        ]

        response = HistoryResponse(
            total=result.get("total", 0),
            page=page,
            limit=limit,
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
            detail="Failed to fetch history"
        )


@router.get(
    "/{processing_id}",
    response_model=RecordResponse,
    summary="Get single record by processing_id",
    tags=["history"]
)
async def get_record(
        request: Request,
        # ✅ CHANGE 2: Use Path() for path parameter
        processing_id: str = Path(..., description="Unique processing identifier"),
) -> RecordResponse:
    """
    Retrieve a single form processing record by processing_id.

    **Path Parameters:**
    - processing_id: Unique identifier returned by upload endpoint

    **Response:**
    - record: Complete form record with all details
    - file_url: MinIO URL for the uploaded file

    **Errors:**
    - 404: Record not found
    - 503: Storage service unavailable

    **Example:**
    ```bash
    curl http://localhost:6000/api/history/proc-abc123def456
    ```
    """
    logger.debug(f"🔍 Fetching record: {processing_id}")

    try:
        # ✅ CHANGE 3: Access storage from app.state
        storage_service = request.app.state.storage

        if not storage_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storage service not available"
            )

        record = await get_record_by_processing_id(storage_service, processing_id)

        if not record:
            logger.warning(f"⚠️  Record not found: {processing_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Record not found: {processing_id}"
            )

        response = RecordResponse(
            record=FormRecord(**record),
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
            detail="Failed to fetch record"
        )


@router.get(
    "/stats/overview",
    response_model=StatsOverview,
    summary="Get statistics overview",
    tags=["history"]
)
async def get_stats_overview(request: Request) -> StatsOverview:
    """
    Retrieve aggregate statistics across all records.

    Includes total count, completion rate, failure count, and average
    confidence score for successfully processed records.

    **Response:**
    - total: Total records processed
    - completed: Successfully completed records
    - failed: Failed processing records
    - pending: Pending/in-progress records
    - average_confidence: Average confidence score
    - completion_rate: Percentage completed

    **Example:**
    ```bash
    curl http://localhost:6000/api/history/stats/overview
    ```
    """
    logger.debug("📊 Fetching statistics overview")

    try:
        # ✅ CHANGE 4: Access storage from app.state
        storage_service = request.app.state.storage

        if not storage_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storage service not available"
            )

        stats = await storage_service.get_statistics()

        response = StatsOverview(
            total=stats.get("total", 0),
            completed=stats.get("completed", 0),
            failed=stats.get("failed", 0),
            pending=stats.get("pending", 0),
            average_confidence=stats.get("average_confidence"),
            completion_rate=stats.get("completion_rate", 0.0),
        )

        logger.debug(f"✅ Retrieved statistics: {response}")
        return response

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"❌ Failed to fetch statistics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch statistics"
        )


@router.delete(
    "/{processing_id}",
    response_model=DeleteResponse,
    summary="Delete a record and associated files",
    tags=["history"]
)
async def delete_record(
        request: Request,
        # ✅ CHANGE 5: Use Path() for path parameter
        processing_id: str = Path(..., description="Unique processing identifier"),
) -> DeleteResponse:
    """
    Delete a form processing record and associated MinIO files.

    Removes both the database record and all uploaded files from
    MinIO object storage. This action cannot be undone.

    **Path Parameters:**
    - processing_id: Unique identifier of record to delete

    **Response:**
    - deleted: Success status
    - processing_id: Deleted identifier
    - message: Deletion details

    **Errors:**
    - 404: Record not found
    - 503: Storage service unavailable

    **Example:**
    ```bash
    curl -X DELETE http://localhost:6000/api/history/proc-abc123def456
    ```
    """
    logger.debug(f"🗑️  Deleting record: {processing_id}")

    try:
        # ✅ CHANGE 6: Access storage from app.state
        storage_service = request.app.state.storage

        if not storage_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storage service not available"
            )

        # Get record first
        record = await get_record_by_processing_id(storage_service, processing_id)

        if not record:
            logger.warning(f"⚠️  Record not found for deletion: {processing_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Record not found: {processing_id}"
            )

        # Delete from storage (handles both MongoDB and MinIO)
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
            message=f"Record and associated files deleted successfully"
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"❌ Failed to delete record {processing_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete record"
        )

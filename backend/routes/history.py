# backend/app/routes/history.py
"""
History route handler for processing records.
Retrieves historical form processing data from MongoDB.
"""

import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Request, HTTPException, status, Query
from pydantic import BaseModel, Field

from config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== RESPONSE MODELS ====================
class FormExtractionData(BaseModel):
    """Extracted form data model."""
    patient_name: Optional[str] = None
    patient_id: Optional[str] = None
    date_of_birth: Optional[str] = None
    form_type: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0, le=1)
    fields: Optional[dict] = None


class ProcessingHistory(BaseModel):
    """Processing history record model."""
    processing_id: str
    status: str
    form_type: str
    timestamp: str
    file_name: Optional[str] = None
    extraction: Optional[FormExtractionData] = None
    confidence: Optional[float] = Field(None, ge=0, le=1)
    error: Optional[str] = None


class HistoryListResponse(BaseModel):
    """Paginated history list response."""
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    items: List[ProcessingHistory]
    has_more: bool


class HistoryStatsResponse(BaseModel):
    """Statistics response model."""
    total_processed: int = Field(..., ge=0)
    completed: int = Field(..., ge=0)
    failed: int = Field(..., ge=0)
    in_progress: int = Field(..., ge=0)
    average_confidence: Optional[float] = Field(None, ge=0, le=1)
    form_types: dict


# ==================== HELPER FUNCTIONS ====================
async def fetch_processing_record(
        mongo_client,
        processing_id: str,
) -> Optional[dict]:
    """
    Fetch a single processing record from MongoDB.

    Args:
        mongo_client: MongoDB client
        processing_id: Record identifier

    Returns:
        Processing record or None
    """
    try:
        record = await mongo_client.find_one(
            collection=settings.MONGODB_DB_COLLECTION,
            query={"processing_id": processing_id}
        )
        return record
    except Exception as e:
        logger.error(f"❌ Database query failed: {e}")
        raise


async def fetch_processing_records(
        mongo_client,
        page: int = 1,
        page_size: int = 20,
        form_type: Optional[str] = None,
        status_filter: Optional[str] = None,
) -> tuple[int, List[dict]]:
    """
    Fetch paginated processing records from MongoDB.

    Args:
        mongo_client: MongoDB client
        page: Page number (1-indexed)
        page_size: Records per page
        form_type: Filter by form type
        status_filter: Filter by status

    Returns:
        Tuple of (total_count, records_list)
    """
    try:
        # Build query
        query = {}
        if form_type:
            query["form_type"] = form_type
        if status_filter:
            query["status"] = status_filter

        # Count total
        total = await mongo_client.count_documents(
            collection=settings.MONGODB_DB_COLLECTION,
            query=query
        )

        # Fetch with pagination
        skip = (page - 1) * page_size
        records = await mongo_client.find(
            collection=settings.MONGODB_DB_COLLECTION,
            query=query,
            sort=[("timestamp", -1)],
            skip=skip,
            limit=page_size
        )

        logger.info(
            f"📊 Fetched {len(records)} records "
            f"(page {page}, total {total})"
        )

        return total, records

    except Exception as e:
        logger.error(f"❌ Database query failed: {e}")
        raise


async def calculate_statistics(mongo_client) -> dict:
    """
    Calculate processing statistics.

    Args:
        mongo_client: MongoDB client

    Returns:
        Statistics dictionary
    """
    try:
        # Get all records
        all_records = await mongo_client.find(
            collection=settings.MONGODB_DB_COLLECTION,
            query={}
        )

        if not all_records:
            return {
                "total_processed": 0,
                "completed": 0,
                "failed": 0,
                "in_progress": 0,
                "average_confidence": None,
                "form_types": {},
            }

        # Calculate stats
        total = len(all_records)
        completed = sum(1 for r in all_records if r.get("status") == "completed")
        failed = sum(1 for r in all_records if r.get("status") == "failed")
        in_progress = sum(1 for r in all_records if r.get("status") == "processing")

        # Calculate average confidence
        confidences = [
            r.get("extraction", {}).get("confidence")
            for r in all_records
            if r.get("extraction", {}).get("confidence") is not None
        ]
        avg_confidence = (
            sum(confidences) / len(confidences) if confidences else None
        )

        # Count form types
        form_types = {}
        for record in all_records:
            ft = record.get("form_type", "UNKNOWN")
            form_types[ft] = form_types.get(ft, 0) + 1

        logger.info(
            f"📈 Statistics: total={total}, completed={completed}, "
            f"failed={failed}, in_progress={in_progress}"
        )

        return {
            "total_processed": total,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "average_confidence": avg_confidence,
            "form_types": form_types,
        }

    except Exception as e:
        logger.error(f"❌ Statistics calculation failed: {e}")
        raise


# ==================== ROUTES ====================
@router.get(
    "/{processing_id}",
    response_model=ProcessingHistory,
    summary="Get processing record",
    tags=["history"]
)
async def get_processing_history(
        processing_id: str = Field(..., description="Processing job ID"),
        request: Request = None,
) -> ProcessingHistory:
    """
    Retrieve a specific processing record by ID.

    Returns the complete processing history including extracted data,
    confidence scores, and any errors that occurred.

    **Path Parameters:**
    - processing_id: Unique identifier from upload response

    **Response:**
    - processing_id: Job identifier
    - status: Processing status (processing, completed, failed)
    - form_type: Detected medical form type (ITF, NAR, etc.)
    - timestamp: Processing timestamp (ISO 8601)
    - extraction: Extracted patient and form data
    - confidence: Overall extraction confidence (0-1)
    - error: Error message if processing failed

    **Errors:**
    - 404: Record not found
    - 503: Service unavailable
    - 500: Database error

    **Example:**
    ```bash
    curl http://localhost:6000/api/history/abc123def456
    ```
    """

    logger.info(f"🔍 History request: {processing_id}")

    try:
        # ✅ CHANGE 1: Access MongoDB from app.state
        mongo_client = request.app.state.mongo

        if not mongo_client:
            logger.error("❌ MongoDB client not initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service not available"
            )

        # ==================== FETCH RECORD ====================
        try:
            record = await fetch_processing_record(mongo_client, processing_id)

            if not record:
                logger.warning(f"⚠️  Record not found: {processing_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Processing record '{processing_id}' not found"
                )

            # ==================== FORMAT RESPONSE ====================
            extraction = record.get("extraction", {})
            confidence = (
                extraction.get("confidence")
                if extraction else None
            )

            logger.info(
                f"✅ Record retrieved: {processing_id} "
                f"(status={record.get('status')})"
            )

            return ProcessingHistory(
                processing_id=processing_id,
                status=record.get("status", "unknown"),
                form_type=record.get("form_type", "UNKNOWN"),
                timestamp=record.get("timestamp", datetime.utcnow().isoformat()),
                file_name=record.get("file_name"),
                extraction=FormExtractionData(
                    patient_name=extraction.get("patient_name"),
                    patient_id=extraction.get("patient_id"),
                    date_of_birth=extraction.get("date_of_birth"),
                    form_type=extraction.get("form_type"),
                    confidence=extraction.get("confidence"),
                    fields=extraction.get("fields"),
                ) if extraction else None,
                confidence=confidence,
                error=record.get("error"),
            )

        except HTTPException:
            raise

        except Exception as e:
            logger.error(f"❌ Record fetch failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve record: {str(e)}"
            )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"❌ History handler error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"History request failed: {str(e)}"
        )


@router.get(
    "/",
    response_model=HistoryListResponse,
    summary="List processing history",
    tags=["history"]
)
async def list_processing_history(
        request: Request,
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        page_size: int = Query(20, ge=1, le=100, description="Records per page"),
        form_type: Optional[str] = Query(None, description="Filter by form type (ITF, NAR)"),
        status: Optional[str] = Query(None, description="Filter by status (processing, completed, failed)"),
) -> HistoryListResponse:
    """
    List all processing records with pagination and filtering.

    Returns a paginated list of form processing records with optional
    filtering by form type and status.

    **Query Parameters:**
    - page: Page number, default 1
    - page_size: Records per page, default 20, max 100
    - form_type: Filter by form type (ITF, NAR, etc.)
    - status: Filter by status (processing, completed, failed)

    **Response:**
    - total: Total number of matching records
    - page: Current page number
    - page_size: Records returned per page
    - items: Array of processing records
    - has_more: Whether more pages exist

    **Errors:**
    - 503: Service unavailable
    - 500: Database error

    **Example:**
    ```bash
    # Get first page
    curl http://localhost:6000/api/history/

    # Get page 2 with 50 items
    curl "http://localhost:6000/api/history/?page=2&page_size=50"

    # Filter by form type
    curl "http://localhost:6000/api/history/?form_type=ITF"

    # Filter by status
    curl "http://localhost:6000/api/history/?status=completed"
    ```
    """

    logger.info(
        f"📋 List history request: "
        f"page={page}, page_size={page_size}, "
        f"form_type={form_type}, status={status}"
    )

    try:
        # ✅ CHANGE 2: Access MongoDB from app.state
        mongo_client = request.app.state.mongo

        if not mongo_client:
            logger.error("❌ MongoDB client not initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service not available"
            )

        # ==================== FETCH RECORDS ====================
        try:
            total, records = await fetch_processing_records(
                mongo_client=mongo_client,
                page=page,
                page_size=page_size,
                form_type=form_type,
                status_filter=status,
            )

            # ==================== FORMAT RESPONSE ====================
            items = []
            for record in records:
                extraction = record.get("extraction", {})
                confidence = (
                    extraction.get("confidence")
                    if extraction else None
                )

                items.append(ProcessingHistory(
                    processing_id=record.get("processing_id", ""),
                    status=record.get("status", "unknown"),
                    form_type=record.get("form_type", "UNKNOWN"),
                    timestamp=record.get("timestamp", datetime.utcnow().isoformat()),
                    file_name=record.get("file_name"),
                    extraction=FormExtractionData(
                        patient_name=extraction.get("patient_name"),
                        patient_id=extraction.get("patient_id"),
                        date_of_birth=extraction.get("date_of_birth"),
                        form_type=extraction.get("form_type"),
                        confidence=extraction.get("confidence"),
                        fields=extraction.get("fields"),
                    ) if extraction else None,
                    confidence=confidence,
                    error=record.get("error"),
                ))

            has_more = (page * page_size) < total

            logger.info(
                f"✅ History listed: {len(items)} records "
                f"(page {page}/{(total + page_size - 1) // page_size})"
            )

            return HistoryListResponse(
                total=total,
                page=page,
                page_size=page_size,
                items=items,
                has_more=has_more,
            )

        except Exception as e:
            logger.error(f"❌ Record fetch failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve records: {str(e)}"
            )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"❌ List handler error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"List request failed: {str(e)}"
        )


@router.get(
    "/stats/overview",
    response_model=HistoryStatsResponse,
    summary="Get processing statistics",
    tags=["history"]
)
async def get_history_stats(
        request: Request,
) -> HistoryStatsResponse:
    """
    Get aggregate statistics about form processing.

    Returns overall statistics including total processed forms,
    success/failure counts, and average confidence.

    **Response:**
    - total_processed: Total number of forms processed
    - completed: Number of successfully completed forms
    - failed: Number of failed processing attempts
    - in_progress: Number of currently processing forms
    - average_confidence: Average extraction confidence (0-1)
    - form_types: Count of forms by type

    **Errors:**
    - 503: Service unavailable
    - 500: Calculation error

    **Example:**
    ```bash
    curl http://localhost:6000/api/history/stats/overview
    ```
    """

    logger.info("📈 Statistics request")

    try:
        # ✅ CHANGE 3: Access MongoDB from app.state
        mongo_client = request.app.state.mongo

        if not mongo_client:
            logger.error("❌ MongoDB client not initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service not available"
            )

        # ==================== CALCULATE STATS ====================
        try:
            stats = await calculate_statistics(mongo_client)

            logger.info(
                f"✅ Statistics calculated: "
                f"total={stats['total_processed']}, "
                f"completed={stats['completed']}"
            )

            return HistoryStatsResponse(
                total_processed=stats["total_processed"],
                completed=stats["completed"],
                failed=stats["failed"],
                in_progress=stats["in_progress"],
                average_confidence=stats["average_confidence"],
                form_types=stats["form_types"],
            )

        except Exception as e:
            logger.error(f"❌ Statistics calculation failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to calculate statistics: {str(e)}"
            )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"❌ Stats handler error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Statistics request failed: {str(e)}"
        )


@router.delete(
    "/{processing_id}",
    summary="Delete processing record",
    tags=["history"]
)
async def delete_processing_record(
        processing_id: str = Field(..., description="Processing job ID"),
        request: Request = None,
) -> dict:
    """
    Delete a processing record and associated files.

    Removes the processing record from the database and deletes
    associated files from MinIO storage.

    **Path Parameters:**
    - processing_id: Unique identifier of record to delete

    **Response:**
    - processing_id: Deleted record identifier
    - deleted: Whether deletion was successful
    - message: Status message

    **Errors:**
    - 404: Record not found
    - 503: Service unavailable
    - 500: Deletion error

    **Example:**
    ```bash
    curl -X DELETE http://localhost:6000/api/history/abc123def456
    ```
    """

    logger.info(f"🗑️  Delete request: {processing_id}")

    try:
        # ✅ CHANGE 4: Access MongoDB from app.state
        mongo_client = request.app.state.mongo
        storage_service = request.app.state.storage

        if not mongo_client or not storage_service:
            logger.error("❌ Services not initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database or storage service not available"
            )

        # ==================== CHECK RECORD EXISTS ====================
        try:
            record = await fetch_processing_record(mongo_client, processing_id)

            if not record:
                logger.warning(f"⚠️  Record not found: {processing_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Processing record '{processing_id}' not found"
                )

            # ==================== DELETE RECORD ====================
            await mongo_client.delete_one(
                collection=settings.MONGODB_DB_COLLECTION,
                query={"processing_id": processing_id}
            )

            logger.info(f"✅ Record deleted from database: {processing_id}")

            # ==================== DELETE FILES ====================
            try:
                # Delete associated files from MinIO
                file_prefix = f"{processing_id}/"
                await storage_service.delete_files_by_prefix(file_prefix)
                logger.info(f"✅ Files deleted from storage: {processing_id}")
            except Exception as e:
                logger.warning(
                    f"⚠️  Failed to delete files from storage: {e} "
                    f"(record already deleted from DB)"
                )

            return {
                "processing_id": processing_id,
                "deleted": True,
                "message": "Processing record and associated files deleted"
            }

        except HTTPException:
            raise

        except Exception as e:
            logger.error(f"❌ Deletion failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete record: {str(e)}"
            )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"❌ Delete handler error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Delete request failed: {str(e)}"
        )

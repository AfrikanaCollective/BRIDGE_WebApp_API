# backend/routes/upload.py
"""
Upload route handler for form processing.
Handles file uploads, validation, and processing pipeline.

"""

import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, UploadFile, File, Request, HTTPException, status
from pydantic import BaseModel

from config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== RESPONSE MODELS ====================
class ProcessingResponse(BaseModel):
    """Response model for file processing."""
    processing_id: str
    status: str
    message: str
    timestamp: str
    file_name: Optional[str] = None
    form_type: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    detail: str
    timestamp: str


# ==================== HELPER FUNCTIONS ====================
async def validate_upload_file(file: UploadFile) -> tuple[bool, Optional[str]]:
    """
    Validate uploaded file.

    Args:
        file: Uploaded file

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check file exists
    if not file or not file.filename:
        return False, "No file provided"

    # Check file size
    file_content = await file.read()
    file_size = len(file_content) / (1024 * 1024)

    if file_size > settings.MAX_FILE_SIZE:
        return False, (
            f"File size {file_size} MBs exceeds maximum "
            f"{settings.MAX_FILE_SIZE} MBs"
        )

    # Reset file pointer for later processing
    await file.seek(0)

    # Check file extension
    file_extension = Path(file.filename).suffix.lower().lstrip('.')
    if file_extension not in settings.ALLOWED_EXTENSIONS:
        return False, (
            f"File type '{file_extension}' not allowed. "
            f"Allowed types: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )

    logger.info(f"✅ File validation passed: {file.filename} ({file_size} MBs)")
    return True, None


async def save_upload_to_temp(file: UploadFile, temp_dir: Path) -> Path:
    """
    Save uploaded file to temporary directory.

    Args:
        file: Uploaded file
        temp_dir: Temporary directory path

    Returns:
        Path to saved file

    Raises:
        HTTPException: If save fails
    """
    try:
        # Ensure temp directory exists
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Create safe filename with timestamp
        # timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        # safe_filename = f"{timestamp}_{file.filename}"
        temp_path = temp_dir / f"{file.filename}"

        # Write file
        content = await file.read()
        temp_path.write_bytes(content)

        # Reset file pointer
        await file.seek(0)

        logger.info(f"📁 File saved to temp: {temp_path}")
        return temp_path

    except Exception as e:
        logger.error(f"❌ Failed to save upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {str(e)}"
        )


# ==================== ROUTES ====================
@router.post(
    "/",
    response_model=ProcessingResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload and process form",
    tags=["upload"]
)
async def upload_file(
        file: UploadFile = File(..., description="Form image file (PNG)"),
        request: Request = None,
) -> ProcessingResponse:
    """
    Upload a medical form image for processing.

    The file is validated, processed through the form processing pipeline,
    and stored in MongoDB/MinIO for later retrieval.

    **Request:**
    - Content-Type: multipart/form-data
    - Field: file (required, PNG image)

    **Response:**
    - processing_id: Unique identifier for tracking processing
    - status: Current processing status
    - message: Human-readable status message

    **Errors:**
    - 400: Invalid file (size, type, format)
    - 503: Service unavailable (processor/storage)
    - 500: Processing error

    **Example:**
    ```bash
    curl -X POST http://localhost:6000/api/upload \\
      -F "file=@form.png"
    ```
    """

    logger.info(f"📤 Upload request: {file.filename}")

    try:
        # ✅ CHANGE 1: Access FormProcessor from app.state
        form_processor = request.app.state.form_processor
        storage_service = request.app.state.storage

        if not form_processor or not storage_service:
            logger.error("❌ Services not initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Form processor or storage service not initialized"
            )

        # ==================== VALIDATE FILE ====================
        is_valid, error_msg = await validate_upload_file(file)
        if not is_valid:
            logger.warning(f"⚠️  File validation failed: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )

        # ==================== SAVE TO TEMP ====================
        temp_dir = Path(settings.UPLOAD_TEMP_DIR)
        temp_path = await save_upload_to_temp(file, temp_dir)
        file_type = form_processor.extract_form_type_from_filename(file.filename)

        # ==================== PROCESS FORM ====================
        logger.info(f"🔄 Processing form: {file.filename}")
        try:
            processing_result = await form_processor.process(
                image_path=str(temp_path),  # ✅ Correct parameter name
                form_type=file_type,  # ✅ default is ITF
                # page_number=None,  # ✅ Optional: auto-detect from filename
                # case_id=None,  # ✅ Optional
                save_to_storage=True,  # ✅ Save to MongoDB/MinIO
                process_with_agent=True,  # ✅ Use form agent
            )

            processing_id = processing_result.get("mongo_id") or str(uuid4())
            form_type = processing_result.get("form_type", "UNKNOWN")
            status_msg = processing_result.get("status", "processing")

            logger.info(
                f"✅ Processing started: {processing_id} "
                f"(form_type={form_type}, status={status_msg})"
            )

            return ProcessingResponse(
                processing_id=processing_id,
                status=status_msg,
                message=f"Form processing initiated. "
                        f"Track progress using processing_id: {processing_id}",
                timestamp=datetime.now(UTC).isoformat(),
                file_name=file.filename,
                form_type=form_type,
            )

        except Exception as e:
            logger.error(f"❌ Processing failed: {e}", exc_info=True)

            # Cleanup temp file on error
            try:
                if temp_path.exists():
                    temp_path.unlink()
                    logger.info(f"🗑️  Cleaned up temp file: {temp_path}")
            except Exception as cleanup_error:
                logger.warning(f"⚠️  Cleanup failed: {cleanup_error}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Form processing failed: {str(e)}"
            )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"❌ Upload handler error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload processing failed: {str(e)}"
        )


@router.get(
    "/status/{processing_id}",
    summary="Get processing status",
    tags=["upload"]
)
async def get_processing_status(
        processing_id: str,
        request: Request,
) -> dict:
    """
    Get the current status of a form processing job.

    **Path Parameters:**
    - processing_id: Unique identifier returned from upload

    **Response:**
    - processing_id: Job identifier
    - status: Current status (processing, completed, failed)
    - progress: Processing progress (0-100)
    - form_type: Detected form type
    - extraction: Extracted data (if completed)
    - error: Error message (if failed)

    **Errors:**
    - 404: Processing job not found
    - 503: Service unavailable

    **Example:**
    ```bash
    curl http://localhost:6000/api/upload/status/abc123def456
    ```
    """

    logger.info(f"📊 Status request: {processing_id}")

    try:
        storage_service = request.app.state.storage

        if not storage_service:
            logger.error("❌ Storage service not initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storage service not available"
            )

        # ==================== FETCH STATUS ====================
        try:
            job_status = await storage_service.get_job_status(processing_id)

            if not job_status:
                logger.warning(f"⚠️  Job not found: {processing_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Processing job '{processing_id}' not found"
                )

            logger.info(
                f"✅ Status retrieved: {processing_id} "
                f"(status={job_status.get('status')})"
            )

            return {
                "processing_id": processing_id,
                "status": job_status.get("status", "unknown"),
                "progress": job_status.get("progress", 0),
                "form_type": job_status.get("form_type"),
                "extraction": job_status.get("extraction"),
                "error": job_status.get("error"),
                "timestamp": job_status.get("timestamp"),
            }

        except HTTPException:
            raise

        except Exception as e:
            logger.error(f"❌ Status fetch failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve status: {str(e)}"
            )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"❌ Status handler error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Status request failed: {str(e)}"
        )


@router.delete(
    "/{processing_id}",
    summary="Cancel processing",
    tags=["upload"]
)
async def cancel_processing(
        processing_id: str,
        request: Request,
) -> dict:
    """
    Cancel an ongoing form processing job.

    **Path Parameters:**
    - processing_id: Unique identifier of job to cancel

    **Response:**
    - processing_id: Job identifier
    - cancelled: Whether cancellation was successful
    - message: Status message

    **Errors:**
    - 404: Processing job not found
    - 409: Job already completed
    - 503: Service unavailable

    **Example:**
    ```bash
    curl -X DELETE http://localhost:6000/api/upload/abc123def456
    ```
    """

    logger.info(f"🚫 Cancel request: {processing_id}")

    try:
        storage_service = request.app.state.storage

        if not storage_service:
            logger.error("❌ Storage service not initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storage service not available"
            )

        # ==================== CANCEL JOB ====================
        try:
            cancel_result = await storage_service.cancel_job(processing_id)

            if cancel_result["success"]:
                logger.info(f"✅ Job cancelled: {processing_id}")
                return {
                    "processing_id": processing_id,
                    "cancelled": True,
                    "message": cancel_result.get("message", "Job cancelled successfully")
                }
            else:
                logger.warning(f"⚠️  Cancellation failed: {cancel_result['reason']}")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=cancel_result.get("reason", "Cannot cancel this job")
                )

        except HTTPException:
            raise

        except Exception as e:
            logger.error(f"❌ Cancellation failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to cancel job: {str(e)}"
            )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"❌ Cancel handler error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cancellation request failed: {str(e)}"
        )

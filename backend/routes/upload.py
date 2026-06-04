# backend/routes/upload.py
"""
Upload route handler for form processing.
Handles file uploads, validation, and processing pipeline.

"""

import logging
from PIL import Image
from uuid import uuid4
from io import BytesIO
from pathlib import Path
from typing import Optional
from datetime import datetime, UTC

from models.upload import ProcessingResponse

from fastapi import APIRouter, UploadFile, File, Request, HTTPException, status, Form

from config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()

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

async def file_exists_in_storage(
        storage_service,
        filename: str,
        s3_key: str,
) -> tuple[bool, Optional[dict]]:
    """
    Check if file already exists in MongoDB and MinIO.

    Args:
        storage_service: Storage service instance
        filename: Image filename
        s3_key: S3 object name (key)

    Returns:
        Tuple of (mongo_exists, minio_exists, document) where document is the existing record if found
    """

    mongo_exists, minio_exists, mongo_doc = False, False, None

    try:
        # Check MongoDB for existing record by filename
        mongo_doc = await storage_service.get_by_image_filename(filename)


        if mongo_doc:
            processing_id = mongo_doc.get("processingId")
            if processing_id:
                logger.info(
                    f"⚠️  File exists in MongoDB database: {filename} "
                    f"(processing_id: {mongo_doc.get('processingId')})"
                )
                mongo_exists = True
            else:
                logger.warning(
                    f"⚠️  Document found but MISSING processingId: {filename} "
                    f"(mongo_id: {mongo_doc.get('_id')}). Treating as non-existent.")
                mongo_exists = False
                mongo_doc = None

        # Also check MinIO to ensure consistency
        minio_exists = storage_service.file_exists_in_minio(s3_key)
        if minio_exists:
            logger.warning(
                f"⚠️  File exists in MinIO: {s3_key}, minio_exists: {minio_exists}"
            )

        return mongo_exists, minio_exists, mongo_doc

    except Exception as e:
        logger.error(f"❌ Error checking file existence: {e}")
        # Don't fail the request, let processing continue
        return False, False, None


def scale_image(image_source, max_width=800):
    """
    Scale image to max width while maintaining aspect ratio and DPI.

    Args:
        image_source: File path (str/Path) or file stream (BytesIO)
        max_width: Maximum width in pixels (default: 800)

    Returns:
        Path object pointing to scaled image file
    """
    img = Image.open(image_source)

    # Get original DPI (default to 150 if not found)
    original_dpi = img.info.get('dpi', (150, 150))

    # Calculate new height maintaining aspect ratio
    aspect_ratio = img.height / img.width
    new_height = int(max_width * aspect_ratio)

    # Resize
    img_resized = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

    # Save to temp file with DPI preserved
    temp_dir = Path(settings.UPLOAD_TEMP_DIR)
    temp_dir.mkdir(parents=True, exist_ok=True)

    output_path = temp_dir / f"scaled_{uuid4()}.png"
    img_resized.save(str(output_path), format='PNG', dpi=original_dpi)

    logger.info(
        f"🖼️  Image scaled: {img.width}x{img.height} → {max_width}x{new_height} "
        f"(DPI: {original_dpi}) → {output_path}"
    )

    return output_path


# ==================== ROUTES ====================
@router.post(
    "",
    response_model=ProcessingResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload and process form",
    tags=["upload"]
)
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
        skip_existing: Optional[bool] = Form(False, description="Skip if file already exists"),
        form_type: Optional[str] = Form(None, description="Override form type detection"),
) -> ProcessingResponse:
    """
    Upload a medical form image for processing.

    The file is validated, processed through the form processing pipeline,
    and stored in MongoDB/MinIO for later retrieval.

    **Request:**
    - Content-Type: multipart/form-data
    - Field: file (required, PNG image)
    - Field: skip_existing (optional, default: false)
    - Field: form_type (optional, auto-detected from filename)

    **Response:**
    - processing_id: Unique identifier for tracking processing
    - status: Current processing status
    - message: Human-readable status message

    **Errors:**
    - 400: Invalid file (size, type, format)
    - 409: File already exists (when skip_existing=true)
    - 503: Service unavailable (processor/storage)
    - 500: Processing error

    **Example:**
    ```bash
    curl -X POST http://localhost:6000/api/upload \\
      -F "file=@form.png"

    # Skip if file already exists
    curl -X POST http://localhost:6000/api/upload \\
      -F "file=@form.png" \\
      -F "skip_existing=true"

    # Override form type
    curl -X POST http://localhost:6000/api/upload \\
      -F "file=@form.png" \\
      -F "form_type=NAR"

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

        # ==================== CHECK IF FILE ALREADY EXISTS ====================

        file_type = form_processor.extract_form_type_from_filename(
            file.filename)
        s3_key = f"form-documents/{file_type.lower()}/{file.filename}"

        mongo_exists, minio_exists, mongo_doc = await file_exists_in_storage(
            storage_service, file.filename, s3_key
        )

        if mongo_exists and minio_exists:
            if skip_existing:
                logger.info(f"⊘ Skipping existing file: {file.filename}")
                return ProcessingResponse(
                    processing_id=mongo_doc.get("processingId"),
                    status=mongo_doc.get("status", "completed"),
                    message=f"File already processed using processing_id: {mongo_doc.get('processingId')}. ",
                    timestamp=datetime.now(UTC).isoformat(),
                    file_name=file.filename,
                    form_type=mongo_doc.get("form_type", "UNKNOWN"),
                )
        # ==================== SAVE TO TEMP ====================
        temp_dir = Path(settings.UPLOAD_TEMP_DIR)
        temp_path = await save_upload_to_temp(file, temp_dir)

        # ==================== RESIZE IMAGE ====================
        # Now resize the file from temp location
        scaled_image_path = scale_image(str(temp_path), max_width=800)
        logger.info(f"🖼️  Image resized and saved to: {scaled_image_path}")

        # ==================== PROCESS FORM ====================
        logger.info(f"🔄 Processing form: {file.filename}")
        try:
            processing_result = await form_processor.process(
                image_path=str(scaled_image_path),  # ✅ Correct parameter name
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
                if scaled_image_path.exists():
                    scaled_image_path.unlink()
                    logger.info(f"🗑️  Cleaned up scaled file: {scaled_image_path}")
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

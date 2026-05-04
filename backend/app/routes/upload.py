# backend/app/routes/upload.py
"""
Upload routes for form processing.
Handles image upload, processing, and storage with MongoDB and MinIO.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status
from pydantic import BaseModel, Field

from app.config.settings import settings
from app.services.form_processor import FormProcessor
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)

router = APIRouter()

# Service instances (injected at runtime)
form_processor: Optional[FormProcessor] = None
storage_service: Optional[StorageService] = None


# ==================== REQUEST/RESPONSE MODELS ====================

class UploadRequest(BaseModel):
    """Request model for form upload."""
    form_type: str = Field(..., description="Type of form (e.g., 'ITF', 'NAR')")
    case_id: Optional[str] = Field(None, description="Case ID for tracking")
    custom_prompt: Optional[str] = Field(None, description="Custom LLM prompt override")


class ProcessingResult(BaseModel):
    """Result model for successful processing."""
    success: bool = Field(True)
    message: str
    document_id: str = Field(..., description="MongoDB document ID")
    minio_original_image_key: str = Field(..., description="S3 key for original image")
    minio_json_results_key: str = Field(..., description="S3 key for full JSON results")
    form_type: str
    case_id: Optional[str]
    timestamp: datetime
    status: str = Field(default="success")


class ProcessingError(BaseModel):
    """Error response model."""
    success: bool = Field(False)
    error: str
    error_code: str
    timestamp: datetime
    details: Optional[dict] = None


class ValidationError(BaseModel):
    """Validation error response model."""
    success: bool = Field(False)
    error: str
    error_code: str = Field(default="VALIDATION_ERROR")
    invalid_fields: Optional[dict] = None


# ==================== ENDPOINTS ====================

@router.post(
    "/form",
    response_model=ProcessingResult,
    responses={
        400: {"model": ValidationError},
        422: {"model": ValidationError},
        500: {"model": ProcessingError},
    },
    summary="Upload and process form",
    description="Upload a form image and process it through the LLM pipeline",
)
async def upload_form(
    file: UploadFile = File(..., description="Form image file"),
    form_type: str = Form(..., description="Type of form (ITF, NAR, etc.)"),
    case_id: Optional[str] = Form(None, description="Case ID for tracking"),
    custom_prompt: Optional[str] = Form(None, description="Custom LLM prompt"),
) -> ProcessingResult:
    """
    Upload and process a form image.

    **Parameters:**
    - `file`: Form image file (PNG, JPG, JPEG, PDF, TIFF)
    - `form_type`: Type of form to process
    - `case_id`: Optional case identifier
    - `custom_prompt`: Optional custom prompt for LLM

    **Response:**
    - `document_id`: MongoDB document ID for result tracking
    - `minio_original_image_key`: S3 location of original image
    - `minio_json_results_key`: S3 location of full JSON results

    **Errors:**
    - 400: Invalid form_type or missing required fields
    - 422: File validation failed (size, format, etc.)
    - 500: Processing error (LLM, storage, etc.)

    **Example:**
    ```bash
    curl -X POST http://localhost:8000/api/upload/form \\
      -F "file=@form.png" \\
      -F "form_type=ITF" \\
      -F "case_id=CASE-12345"
    ```
    """

    # Validate service injection
    if form_processor is None or storage_service is None:
        logger.error("❌ Services not initialized")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Services not initialized. Please restart the application."
        )

    # ==================== VALIDATION ====================

    # Validate form_type
    valid_form_types = ["ITF", "NAR", "MISC"]
    if form_type.upper() not in valid_form_types:
        logger.warning(f"❌ Invalid form_type: {form_type}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid form_type: {form_type}. Must be one of {valid_form_types}"
        )

    # Validate file
    if file.size is None or file.size == 0:
        logger.warning("❌ Empty file uploaded")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File is empty"
        )

    max_size_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if file.size > max_size_bytes:
        logger.warning(f"❌ File too large: {file.size} bytes")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File size exceeds maximum: {settings.MAX_UPLOAD_SIZE_MB}MB"
        )

    # Validate file extension
    if not file.filename:
        logger.warning("❌ File has no name")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File has no name"
        )

    file_ext = file.filename.rsplit(".", 1)[-1].lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        logger.warning(f"❌ Invalid file extension: {file_ext}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid file extension: {file_ext}. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )

    # ==================== PROCESSING ====================
    processing_id = str(uuid.uuid4())
    timestamp = datetime.utcnow()

    try:
        logger.info(f"📥 Processing upload: {processing_id}")
        logger.info(f"   Form Type: {form_type}")
        logger.info(f"   Case ID: {case_id or 'N/A'}")
        logger.info(f"   File: {file.filename} ({file.size} bytes)")

        # Read file content
        file_content = await file.read()

        # Process form through pipeline
        result = await form_processor.process(
            image_bytes=file_content,
            filename=file.filename,
            form_type=form_type.upper(),
            case_id=case_id,
            custom_prompt=custom_prompt,
        )

        if not result.get("success"):
            logger.error(f"❌ Processing failed: {result.get('error')}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Processing failed")
            )

        # ==================== STORAGE ====================

        logger.info(f"💾 Storing results for: {processing_id}")

        # Store in MongoDB and MinIO
        storage_result = await storage_service.save(
            document_metadata={
                "form_type": form_type.upper(),
                "case_id": case_id,
                "timestamp": timestamp,
                "image_filename": file.filename,
                "file_size_mb": file.size / (1024 * 1024),
                "processing_id": processing_id,
            },
            original_image_bytes=file_content,
            original_image_filename=file.filename,
            processing_result=result,
        )

        if not storage_result.get("success"):
            logger.error(f"❌ Storage failed: {storage_result.get('error')}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=storage_result.get("error", "Storage failed")
            )

        # ==================== SUCCESS RESPONSE ====================

        logger.info(f"✅ Upload completed successfully: {processing_id}")
        logger.info(f"   MongoDB ID: {storage_result['document_id']}")
        logger.info(f"   Image S3 Key: {storage_result['minio_original_image_key']}")
        logger.info(f"   JSON S3 Key: {storage_result['minio_json_results_key']}")

        return ProcessingResult(
            success=True,
            message="Form processed and stored successfully",
            document_id=storage_result["document_id"],
            minio_original_image_key=storage_result["minio_original_image_key"],
            minio_json_results_key=storage_result["minio_json_results_key"],
            form_type=form_type.upper(),
            case_id=case_id,
            timestamp=timestamp,
            status="success",
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        logger.error(f"❌ Unexpected error processing upload: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )


@router.post(
    "/form-batch",
    response_model=dict,
    summary="Batch upload forms",
    description="Upload multiple forms for processing",
)
async def upload_form_batch(
    files: list[UploadFile] = File(...),
    form_type: str = Form(...),
    case_id: Optional[str] = Form(None),
) -> dict:
    """
    Upload multiple forms in batch.

    **Parameters:**
    - `files`: List of form image files
    - `form_type`: Type of form for all files
    - `case_id`: Optional case identifier

    **Response:**
    - `successful`: List of successfully processed results
    - `failed`: List of failed uploads with error details

    **Example:**
    ```bash
    curl -X POST http://localhost:8000/api/upload/form-batch \\
      -F "files=@form1.png" \\
      -F "files=@form2.png" \\
      -F "form_type=ITF" \\
      -F "case_id=CASE-12345"
    ```
    """

    if form_processor is None or storage_service is None:
        logger.error("❌ Services not initialized")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Services not initialized"
        )

    successful = []
    failed = []

    for file in files:
        try:
            logger.info(f"📥 Processing batch file: {file.filename}")

            # Validate file
            if file.size is None or file.size == 0:
                failed.append({
                    "filename": file.filename,
                    "error": "File is empty"
                })
                continue

            max_size_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
            if file.size > max_size_bytes:
                failed.append({
                    "filename": file.filename,
                    "error": f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit"
                })
                continue

            # Process file
            file_content = await file.read()

            result = await form_processor.process(
                image_bytes=file_content,
                filename=file.filename,
                form_type=form_type.upper(),
                case_id=case_id,
            )

            if not result.get("success"):
                failed.append({
                    "filename": file.filename,
                    "error": result.get("error", "Processing failed")
                })
                continue

            # Store result
            storage_result = await storage_service.save(
                document_metadata={
                    "form_type": form_type.upper(),
                    "case_id": case_id,
                    "timestamp": datetime.utcnow(),
                    "image_filename": file.filename,
                    "file_size_mb": file.size / (1024 * 1024),
                },
                original_image_bytes=file_content,
                original_image_filename=file.filename,
                processing_result=result,
            )

            if storage_result.get("success"):
                successful.append({
                    "filename": file.filename,
                    "document_id": storage_result["document_id"],
                    "image_key": storage_result["minio_original_image_key"],
                    "json_key": storage_result["minio_json_results_key"],
                })
            else:
                failed.append({
                    "filename": file.filename,
                    "error": storage_result.get("error", "Storage failed")
                })

        except Exception as e:
            logger.error(f"❌ Error processing {file.filename}: {e}")
            failed.append({
                "filename": file.filename,
                "error": str(e)
            })

    logger.info(f"✅ Batch processing complete: {len(successful)} successful, {len(failed)} failed")

    return {
        "total": len(files),
        "successful": len(successful),
        "failed": len(failed),
        "results": {
            "successful": successful,
            "failed": failed,
        }
    }


@router.get(
    "/status/{processing_id}",
    response_model=dict,
    summary="Get processing status",
    description="Get the status of a form processing job",
)
async def get_processing_status(processing_id: str) -> dict:
    """
    Get status of a processing job.

    **Parameters:**
    - `processing_id`: Unique processing identifier

    **Response:**
    - `status`: Current status (pending, processing, success, error)
    - `timestamp`: When the job was created
    - `result`: Processing result if completed

    **Example:**
    ```bash
    curl http://localhost:8000/api/upload/status/abc123def456
    ```
    """

    if storage_service is None:
        logger.error("❌ Services not initialized")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Services not initialized"
        )

    try:
        # Query MongoDB for processing_id
        collection = storage_service.mongo_client.get_collection(
            storage_service.collection_name
        )

        document = collection.find_one({"processing_id": processing_id})

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Processing ID not found: {processing_id}"
            )

        return {
            "processing_id": processing_id,
            "status": document.get("status", "unknown"),
            "timestamp": document.get("timestamp"),
            "form_type": document.get("form_type"),
            "case_id": document.get("case_id"),
            "document_id": str(document.get("_id")),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving status"
        )

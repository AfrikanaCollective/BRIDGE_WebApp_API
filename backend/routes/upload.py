# backend/routes/upload.py
"""
Upload route handler for form processing.
Handles file uploads, validation, and processing pipeline.

"""

import time
import logging
from PIL import Image
from io import BytesIO
from uuid import uuid4
from pathlib import Path
import pypdfium2 as pdfium
from typing import Optional
from datetime import datetime, UTC

from models.upload import ProcessingResponse
from config.preprocessing_profiles import get_profile
from services.preprocessing import AdaptivePreprocessor

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
        return [str(temp_path)]

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

async def convert_pdf_to_png(pdf_source) -> list[str]:
    """
    Convert PDF pages to PNG images with max width constraint.
    Saves converted PNGs to UPLOAD_TEMP_DIR for processing.

    Args:
        pdf_source: File path (str/Path) or file stream (BytesIO)

    Returns:
        List of Path strings pointing to converted PNG files

    Raises:
        HTTPException: If PDF processing fails
    """

    temp_dir = Path(settings.UPLOAD_TEMP_DIR)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # ==================== HANDLE DIFFERENT INPUT TYPES ====================
        if isinstance(pdf_source, (str, Path)):
            # File path provided
            pdf_path = Path(pdf_source)
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            pdf = pdfium.PdfDocument(str(pdf_path))
            pdf_name = pdf_path.name
        else:
            # UploadFile object provided
            # Read the uploaded file into memory
            pdf_content = await pdf_source.read()
            pdf = pdfium.PdfDocument(pdf_content)
            pdf_name = pdf_source.filename

        file_root = pdf_name.replace(".pdf", "")
        n_pages = len(pdf)  # get the number of pages in the document

        page_indices = [i for i in range(n_pages)]  # all pages
        converted_files = []

        # Calculate scale factor for 300 DPI (300/72 ≈ 4.17x)
        dpi_scale = 300 / 72

        for page_num in page_indices:
            output_file = temp_dir / f"{file_root}_page_{page_num + 1}.png"
            page = pdf[page_num] # Select the page object (PdfPage)

            # Render directly to PIL Image at specified DPI
            pil_image = page.render(
                scale=dpi_scale,
                rotation=0
            ).to_pil()

            pil_image.save(str(output_file), dpi=(300, 300))
            converted_files.append(str(output_file))
            logger.info(
                f"📄 PDF page converted: {file_root} (page {page_num + 1}) "
                f"→ {output_file}"
            )

        logger.info(
            f"✅ PDF conversion complete: {pdf_name} "
            f"({n_pages} pages) → {temp_dir}"
        )

        return converted_files

    except ImportError:
        logger.error("❌ pdfium module not installed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF processing library not available"
        )

    except Exception as e:
        logger.error(f"❌ PDF conversion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to convert PDF: {str(e)}"
        )

async def convert_jpg_to_png(jpg_source) -> list[str]:
    """
    Convert JPG/JPEG images to PNG format at 300 DPI.
    Saves converted PNGs to UPLOAD_TEMP_DIR for processing.

    Args:
        jpg_source: File path (str/Path) or file stream (UploadFile)

    Returns:
        List of Path strings pointing to converted PNG files

    Raises:
        HTTPException: If JPG processing fails
    """

    temp_dir = Path(settings.UPLOAD_TEMP_DIR)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # ==================== HANDLE DIFFERENT INPUT TYPES ====================
        if isinstance(jpg_source, (str, Path)):
            # File path provided
            jpg_path = Path(jpg_source)
            if not jpg_path.exists():
                raise FileNotFoundError(f"JPG file not found: {jpg_path}")
            pil_image = Image.open(jpg_path)
            jpg_name = jpg_path.name
        else:
            # UploadFile object provided
            # Read the uploaded file into memory
            jpg_content = await jpg_source.read()
            pil_image = Image.open(BytesIO(jpg_content))
            jpg_name = jpg_source.filename

        # Convert RGBA/other formats to RGB if necessary (PNG requires RGB for JPG conversion)
        if pil_image.mode in ("RGBA", "LA", "P"):
            # Create white background for transparency
            background = Image.new("RGB", pil_image.size, (255, 255, 255))
            background.paste(pil_image, mask=pil_image.split()[-1] if pil_image.mode == "RGBA" else None)
            pil_image = background
        elif pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")

        file_root = jpg_name.rsplit(".", 1)[0]  # Remove extension
        output_file = temp_dir / f"{file_root}.png"

        # Save as PNG at 300 DPI
        pil_image.save(str(output_file), dpi=(300, 300))
        converted_files = [str(output_file)]

        logger.info(
            f"🖼️  JPG converted: {jpg_name} → {output_file} "
            f"({pil_image.width}x{pil_image.height}px @ 300 DPI)"
        )

        return converted_files

    except ImportError:
        logger.error("❌ PIL/Pillow module not installed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Image processing library not available"
        )

    except FileNotFoundError as e:
        logger.error(f"❌ JPG file not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File not found: {str(e)}"
        )

    except Exception as e:
        logger.error(f"❌ JPG conversion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to convert JPG: {str(e)}"
        )


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

    # ==================== SAVE TO TEMP ====================
    temp_dir = Path(settings.UPLOAD_TEMP_DIR)

    try:
        # Access FormProcessor from app.state
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

        # ==================== DETERMINE FILE TYPE & PROCESS ====================
        file_extension = Path(file.filename).suffix.lower().lstrip('.')
        if file_extension == "pdf":
            png_files = await convert_pdf_to_png(file)
        elif file_extension in ["jpg", "jpeg"]:
            png_files = await convert_jpg_to_png(file)
        elif file_extension == "png":
            png_files = await save_upload_to_temp(file, temp_dir)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format: {file_extension}"
            )

        logger.info(f"🔄 Files to process: {png_files}")

        # ==================== GET FILE TYPE ====================
        file_type = form_processor.extract_form_type_from_filename(file.filename)
        logger.info(f"📋 Extracted form type: {file_type}")

        # ==================== GET PRE-PROCESSOR ====================
        profile = get_profile("HANDWRITTEN") # Get preprocessing profile
        preprocessor = AdaptivePreprocessor(profile=profile)

        logger.info(f"Using preprocessing profile for: {file_type or 'ITF (default)'}")

        # ==================== PROCESS EACH PNG FILE ====================
        processing_ids = []
        processing_errors = []
        primary_processing_id = None
        primary_form_type = None
        first_existing_id = None

        for idx, png_file in enumerate(png_files):
            png_path = Path(png_file)
            png_filename = png_path.name
            scaled_image_path = None

            try:
                logger.info(f"📄 Processing file {idx + 1}/{len(png_files)}: {png_filename}")

                # ==================== CHECK IF FILE ALREADY EXISTS ====================
                s3_key = f"form-documents/{file_type.lower()}/{png_filename}"
                logger.info(f"S3 file key: {s3_key}")

                mongo_exists, minio_exists, mongo_doc = await file_exists_in_storage(
                    storage_service, png_filename, s3_key
                )

                if mongo_exists and minio_exists:
                    if skip_existing:
                        logger.info(f"⊘ Skipping existing file: {png_filename}")
                        existing_id = mongo_doc.get("processingId")
                        processing_ids.append(existing_id)

                        # Store first page details for response
                        if primary_processing_id is None:
                            primary_processing_id = existing_id
                            primary_form_type = mongo_doc.get("form_type", file_type)
                            first_existing_id = existing_id

                        continue  # Skip to next file
                    else:
                        # File exists but skip_existing is False, so overwrite
                        logger.info(f"⚠️  File exists but overwriting: {png_filename}")

                # ==================== PREPROCESS & RESIZE (UNIFIED) ====================
                t_preprocess_start = time.time()

                processed_file_path = preprocessor.preprocess(
                    image=str(png_path),
                    current_dpi=300,
                    resize_to_width=800,
                    save_to_temp=True,
                    original_filename=png_filename  # ← Maintains original filename
                )

                preprocess_time = time.time() - t_preprocess_start

                processed_image = Image.open(processed_file_path)
                logger.info(
                    f"🎨 Page {idx + 1} preprocessed & resized: {processed_image.size} "
                    f"({processed_image.size[0] * processed_image.size[1]:,} pixels) "
                    f"in {preprocess_time:.3f}s → {processed_file_path}"
                )

                # ==================== PROCESS FORM ====================
                logger.info(f"🔄 Processing form: {png_filename}")

                processing_result = await form_processor.process(
                    image_path=str(processed_file_path),
                    form_type=file_type,
                    # page_number=idx + 1,  # ✅ Optional: page number for multi-page docs
                    # case_id=None,  # ✅ Optional
                    save_to_storage=True,
                    process_with_agent=True,
                )

                processing_id = processing_result.get("mongo_id") or str(uuid4())
                form_type_result = processing_result.get("form_type", file_type)
                status_msg = processing_result.get("status", "processing")

                processing_ids.append(processing_id)

                # Store first page details for response
                if primary_processing_id is None:
                    primary_processing_id = processing_id
                    primary_form_type = form_type_result

                logger.info(
                    f"✅ Processing started: {processing_id} "
                    f"(form_type={form_type_result}, status={status_msg}, "
                    f"page {idx + 1}/{len(png_files)})"
                )

                # ==================== CLEANUP SCALED IMAGE ====================
                try:
                    if scaled_image_path and Path(scaled_image_path).exists():
                        Path(scaled_image_path).unlink()
                        logger.info(f"🗑️  Cleaned up scaled file: {scaled_image_path}")
                except Exception as cleanup_error:
                    logger.warning(f"⚠️  Failed to cleanup scaled file: {cleanup_error}")

            except Exception as e:
                logger.error(
                    f"❌ Processing failed for file {idx + 1}/{len(png_files)}: {e}",
                    exc_info=True
                )
                processing_errors.append({
                    "file": png_filename,
                    "page": idx + 1,
                    "error": str(e)
                })

                # Cleanup on error
                try:
                    if scaled_image_path and Path(scaled_image_path).exists():
                        Path(scaled_image_path).unlink()
                        logger.info(f"🗑️  Cleaned up scaled file after error: {scaled_image_path}")
                except Exception as cleanup_error:
                    logger.warning(f"⚠️  Failed to cleanup: {cleanup_error}")

                continue  # Continue processing remaining pages

        # ==================== FINAL CLEANUP ====================
        # Delete all converted PNG files
        for png_file in png_files:
            try:
                png_path = Path(png_file)
                if png_path.exists():
                    png_path.unlink()
                    logger.info(f"🗑️  Cleaned up PNG file: {png_file}")
            except Exception as cleanup_error:
                logger.warning(f"⚠️  Failed to cleanup PNG file: {cleanup_error}")

        # ==================== VALIDATE PROCESSING RESULTS ====================
        if not processing_ids:
            error_details = (
                "\n".join([f"  - {e['file']} (page {e['page']}): {e['error']}"
                           for e in processing_errors])
                if processing_errors else "Unknown error"
            )
            logger.error(f"❌ All processing attempts failed:\n{error_details}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Form processing failed for all pages. Details: {error_details}"
            )

        # ==================== BUILD RESPONSE MESSAGE ====================
        if first_existing_id:
            response_message = (
                f"All {len(processing_ids)} pages already processed. "
                f"Primary processing_id: {primary_processing_id}"
            )
        else:
            response_message = (
                f"Form processing initiated for {len(processing_ids)}/{len(png_files)} pages. "
                f"Track progress using primary processing_id: {primary_processing_id}"
            )

        if processing_errors:
            response_message += f"\n⚠️  {len(processing_errors)} page(s) failed: " \
                                f"{', '.join([e['file'] for e in processing_errors])}"
            logger.warning(f"⚠️  Processing completed with errors: {processing_errors}")

        # ==================== RETURN RESPONSE ====================
        return ProcessingResponse(
            processing_id=primary_processing_id,
            status="processing" if not first_existing_id else "completed",
            message=response_message,
            timestamp=datetime.now(UTC).isoformat(),
            file_name=file.filename,
            form_type=primary_form_type,
            page_count=len(processing_ids),
            total_pages=len(png_files),
            processing_ids=processing_ids,
            errors=processing_errors if processing_errors else None,
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

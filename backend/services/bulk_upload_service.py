# backend/services/bulk_upload_service.py
"""
Bulk upload service for processing multiple forms from a directory.
Allows programmatic iteration and processing of files without HTTP requests.
"""

import logging
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime, UTC

logger = logging.getLogger(__name__)


@dataclass
class BulkUploadResult:
    """Result of a single file processing."""
    filename: str
    success: bool
    mongo_id: Optional[str] = None
    form_type: Optional[str] = None
    error: Optional[str] = None
    processing_time_seconds: Optional[float] = None
    file_size_mb: Optional[float] = None


@dataclass
class BulkUploadSummary:
    """Summary of bulk upload operation."""
    total_files: int
    successful: int
    failed: int
    skipped: int
    total_size_mb: float
    total_processing_time_seconds: float
    results: List[BulkUploadResult]
    start_time: str
    end_time: str


class BulkUploadService:
    """
    Service for bulk uploading and processing forms from a directory.

    Provides a programmatic interface to process multiple files without
    going through the HTTP upload endpoint.
    """

    def __init__(
            self,
            form_processor,
            storage_service,
            allowed_extensions: Optional[List[str]] = None,
            max_file_size_mb: float = 50,
    ):
        """
        Initialize bulk upload service.

        Args:
            form_processor: FormProcessor instance for processing
            storage_service: StorageService instance for persistence
            allowed_extensions: List of allowed file extensions (e.g., ['png', 'pdf'])
            max_file_size_mb: Maximum file size in MB
        """
        self.form_processor = form_processor
        self.storage_service = storage_service
        self.allowed_extensions = allowed_extensions or ['png', 'jpg', 'jpeg', 'pdf']
        self.max_file_size_mb = max_file_size_mb

        logger.info(
            f"🚀 BulkUploadService initialized: "
            f"extensions={self.allowed_extensions}, "
            f"max_size={max_file_size_mb}MB"
        )

    def _validate_file(self, file_path: Path) -> tuple[bool, Optional[str]]:
        """
        Validate a file before processing.

        Args:
            file_path: Path to file

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check file exists
        if not file_path.exists():
            return False, f"File not found: {file_path}"

        # Check file is readable
        if not file_path.is_file():
            return False, f"Not a file: {file_path}"

        # Check file extension
        extension = file_path.suffix.lower().lstrip('.')
        if extension not in self.allowed_extensions:
            return False, (
                f"File type '{extension}' not allowed. "
                f"Allowed: {', '.join(self.allowed_extensions)}"
            )

        # Check file size
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > self.max_file_size_mb:
            return False, (
                f"File size {file_size_mb:.2f}MB exceeds "
                f"maximum {self.max_file_size_mb}MB"
            )

        logger.debug(f"✅ File validation passed: {file_path.name} ({file_size_mb:.2f}MB)")
        return True, None

    async def process_single_file(
            self,
            file_path: str,
            form_type: Optional[str] = None,
            case_id: Optional[str] = None,
            page_number: Optional[int] = None,
            process_with_agent: bool = True,
    ) -> BulkUploadResult:
        """
        Process a single file programmatically.

        Args:
            file_path: Path to file to process
            form_type: Form type (auto-detected if None)
            case_id: Optional case ID
            page_number: Optional page number
            process_with_agent: Whether to use form agent

        Returns:
            BulkUploadResult with success/error details
        """
        file_path = Path(file_path)
        start_time = datetime.now(UTC)

        try:
            # ==================== VALIDATE ====================
            is_valid, error_msg = self._validate_file(file_path)
            if not is_valid:
                logger.warning(f"⚠️  Validation failed: {file_path.name} - {error_msg}")
                return BulkUploadResult(
                    filename=file_path.name,
                    success=False,
                    error=error_msg,
                )

            # ==================== GET FILE SIZE ====================
            file_size_mb = file_path.stat().st_size / (1024 * 1024)

            # ==================== AUTO-DETECT FORM TYPE ====================
            if not form_type:
                form_type = self.form_processor.extract_form_type_from_filename(
                    file_path.name
                )
                logger.info(f"📋 Auto-detected form type: {form_type}")

            # ==================== PROCESS ====================
            logger.info(
                f"🔄 Processing: {file_path.name} "
                f"(type={form_type}, size={file_size_mb:.2f}MB)"
            )

            processing_result = await self.form_processor.process(
                image_path=str(file_path),
                form_type=form_type,
                page_number=page_number,
                case_id=case_id,
                save_to_storage=True,
                process_with_agent=process_with_agent,
            )

            # ==================== EXTRACT RESULT ====================
            mongo_id = processing_result.get("mongo_id")
            status = processing_result.get("status")
            error = processing_result.get("error")

            processing_time = (datetime.now(UTC) - start_time).total_seconds()

            if status == "success" and mongo_id:
                logger.info(
                    f"✅ Processed successfully: {file_path.name} "
                    f"(id={mongo_id}, time={processing_time:.2f}s)"
                )
                return BulkUploadResult(
                    filename=file_path.name,
                    success=True,
                    mongo_id=mongo_id,
                    form_type=form_type,
                    processing_time_seconds=processing_time,
                    file_size_mb=file_size_mb,
                )
            else:
                error_msg = error or "Processing returned no ID"
                logger.error(
                    f"❌ Processing failed: {file_path.name} - {error_msg}"
                )
                return BulkUploadResult(
                    filename=file_path.name,
                    success=False,
                    form_type=form_type,
                    error=error_msg,
                    processing_time_seconds=processing_time,
                    file_size_mb=file_size_mb,
                )

        except Exception as e:
            processing_time = (datetime.now(UTC) - start_time).total_seconds()
            logger.error(
                f"❌ Exception processing {file_path.name}: {e}",
                exc_info=True
            )
            return BulkUploadResult(
                filename=file_path.name,
                success=False,
                error=str(e),
                processing_time_seconds=processing_time,
                file_size_mb=file_size_mb,
            )

    async def process_directory(
            self,
            directory_path: str,
            form_type: Optional[str] = None,
            case_id: Optional[str] = None,
            recursive: bool = False,
            process_with_agent: bool = True,
            skip_existing: bool = False,
    ) -> BulkUploadSummary:
        """
        Process all files in a directory.

        Args:
            directory_path: Path to directory containing files
            form_type: Form type for all files (auto-detect if None)
            case_id: Optional case ID for all files
            recursive: If True, process subdirectories recursively
            process_with_agent: Whether to use form agent
            skip_existing: If True, skip files already in database by filename

        Returns:
            BulkUploadSummary with overall results
        """
        directory = Path(directory_path)

        if not directory.exists():
            raise ValueError(f"Directory not found: {directory_path}")

        if not directory.is_dir():
            raise ValueError(f"Not a directory: {directory_path}")

        logger.info(
            f"📂 Starting bulk upload from: {directory} "
            f"(recursive={recursive}, skip_existing={skip_existing})"
        )

        # ==================== COLLECT FILES ====================
        files_to_process = []

        if recursive:
            pattern = "**/*"
        else:
            pattern = "*"

        for file_path in directory.glob(pattern):
            if not file_path.is_file():
                continue

            extension = file_path.suffix.lower().lstrip('.')
            if extension not in self.allowed_extensions:
                logger.debug(
                    f"⏭️  Skipping unsupported file type: {file_path.name}"
                )
                continue

            files_to_process.append(file_path)

        if not files_to_process:
            logger.warning(f"⚠️  No files found to process in: {directory}")
            return BulkUploadSummary(
                total_files=0,
                successful=0,
                failed=0,
                skipped=0,
                total_size_mb=0,
                total_processing_time_seconds=0,
                results=[],
                start_time=datetime.now(UTC).isoformat(),
                end_time=datetime.now(UTC).isoformat(),
            )

        logger.info(f"📋 Found {len(files_to_process)} files to process")

        # ==================== PROCESS FILES ====================
        results: List[BulkUploadResult] = []
        total_size_mb = 0
        total_time = 0
        skipped_count = 0
        start_time = datetime.now(UTC)

        for idx, file_path in enumerate(files_to_process, 1):
            logger.info(
                f"[{idx}/{len(files_to_process)}] Processing: {file_path.name}"
            )

            # ==================== CHECK IF EXISTS (optional) ====================
            if skip_existing:
                existing = await self.storage_service.collection.find_one(
                    {"image_filename": file_path.name}
                )
                if existing:
                    logger.info(
                        f"⏭️  Skipping existing file: {file_path.name} "
                        f"(id={existing.get('_id')})"
                    )
                    skipped_count += 1
                    results.append(
                        BulkUploadResult(
                            filename=file_path.name,
                            success=True,
                            mongo_id=str(existing.get("_id")),
                            error="Skipped (already exists)",
                        )
                    )
                    continue

            # ==================== PROCESS ====================
            result = await self.process_single_file(
                file_path=str(file_path),
                form_type=form_type,
                case_id=case_id,
                process_with_agent=process_with_agent,
            )

            results.append(result)

            if result.success:
                total_size_mb += result.file_size_mb or 0
                total_time += result.processing_time_seconds or 0

        end_time = datetime.now(UTC)

        # ==================== GENERATE SUMMARY ====================
        successful = sum(1 for r in results if r.success and r.mongo_id)
        failed = sum(1 for r in results if not r.success or not r.mongo_id)
        skipped = skipped_count

        summary = BulkUploadSummary(
            total_files=len(files_to_process),
            successful=successful,
            failed=failed,
            skipped=skipped,
            total_size_mb=round(total_size_mb, 2),
            total_processing_time_seconds=round(total_time, 2),
            results=results,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
        )

        # ==================== LOG SUMMARY ====================
        logger.info(
            f"✨ BULK UPLOAD COMPLETE:\n"
            f"  📊 Total: {summary.total_files}\n"
            f"  ✅ Success: {successful}\n"
            f"  ❌ Failed: {failed}\n"
            f"  ⏭️  Skipped: {skipped}\n"
            f"  📦 Total Size: {summary.total_size_mb}MB\n"
            f"  ⏱️  Total Time: {summary.total_processing_time_seconds}s"
        )

        return summary

    def print_summary(self, summary: BulkUploadSummary) -> None:
        """
        Pretty-print bulk upload summary.

        Args:
            summary: BulkUploadSummary object
        """
        print("\n" + "=" * 80)
        print("BULK UPLOAD SUMMARY")
        print("=" * 80)
        print(f"Start Time:    {summary.start_time}")
        print(f"End Time:      {summary.end_time}")
        print(f"\nTotal Files:   {summary.total_files}")
        print(f"✅ Successful: {summary.successful}")
        print(f"❌ Failed:     {summary.failed}")
        print(f"⏭️  Skipped:    {summary.skipped}")
        print(f"\nTotal Size:    {summary.total_size_mb} MB")
        print(f"Total Time:    {summary.total_processing_time_seconds} seconds")
        print("-" * 80)

        if summary.results:
            print("\nDETAILED RESULTS:")
            print("-" * 80)
            for result in summary.results:
                status_icon = "✅" if result.success else "❌"
                print(f"{status_icon} {result.filename}")
                if result.mongo_id:
                    print(f"   ID: {result.mongo_id}")
                if result.form_type:
                    print(f"   Type: {result.form_type}")
                if result.file_size_mb:
                    print(f"   Size: {result.file_size_mb:.2f} MB")
                if result.processing_time_seconds:
                    print(f"   Time: {result.processing_time_seconds:.2f}s")
                if result.error:
                    print(f"   Error: {result.error}")
                print()

        print("=" * 80 + "\n")

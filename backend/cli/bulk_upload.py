# backend/cli/bulk_upload.py
"""
CLI utility for bulk uploading and processing form images directly via the LLM gateway.

Usage:
    python -m backend.cli.bulk_upload --directory ./bridge_images
    python -m backend.cli.bulk_upload --directory ./bridge_images --recursive
    python -m backend.cli.bulk_upload --directory ./bridge_images --skip-existing
    python -m backend.cli.bulk_upload --file ./bridge_images/form_001.png --form-type ITF
    python -m backend.cli.bulk_upload --directory ./bridge_images --concurrency 5 --max-retries 4
    python -m backend.cli.bulk_upload --file /opt/bridge_images/NAR_72001218_page_1.png --form-type NAR --max-retries 3
"""

import sys
import asyncio
import logging
import random
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field

# When invoked as `python -m backend.cli.bulk_upload` from the project root,
# `backend/` is not automatically on sys.path. Insert it so that the same
# absolute imports used by main.py and server.py resolve correctly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import click

from config.settings import settings
from clients.mongo_client import MongoClient
from clients.minio_client import MinIOClient
from services.storage_service import StorageService
from services.form_processor import FormProcessor

ALLOWED_EXTENSIONS = settings.ALLOWED_EXTENSIONS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    """Result of a single file upload."""
    file_path: Path
    success: bool
    processing_id: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None
    form_type: Optional[str] = None
    skipped: bool = False


@dataclass
class BulkUploadSummary:
    """Summary of bulk upload results."""
    total_files: int
    successful_uploads: int
    failed_uploads: int
    skipped_files: int
    total_processing_time_seconds: float
    errors: List[str] = field(default_factory=list)


class BulkUploadCLI:
    """
    Bulk upload handler that calls FormProcessor directly,
    bypassing the HTTP layer entirely.
    """

    def __init__(self):
        self.form_processor: Optional[FormProcessor] = None
        self.mongo_client: Optional[MongoClient] = None
        self.minio_client: Optional[MinIOClient] = None
        self.results: List[UploadResult] = []

    # ==================== SERVICE LIFECYCLE ====================

    async def _init_services(self) -> None:
        """
        Bootstrap MongoDB, MinIO, StorageService and FormProcessor
        using the same configuration path as main.py lifespan.
        """
        logger.info("🔧 Initializing services...")

        mongo_client = MongoClient(
            uri=settings.get_mongodb_uri(),
            db_name=settings.MONGODB_DB_NAME,
        )
        health = await mongo_client.health_check()
        if not health["connected"]:
            raise RuntimeError(f"MongoDB health check failed: {health.get('error')}")
        logger.info(f"✅ MongoDB connected: {settings.MONGODB_DB_NAME}")

        minio_cfg = settings.get_minio_config()
        minio_client = MinIOClient(
            endpoint=minio_cfg["endpoint"],
            access_key=minio_cfg["access_key"],
            secret_key=minio_cfg["secret_key"],
            bucket_name=minio_cfg["bucket_name"],
            secure=minio_cfg["secure"],
            region=minio_cfg["region"],
        )
        await minio_client.ensure_bucket_exists()
        logger.info(f"✅ MinIO connected: {minio_cfg['bucket_name']}")

        storage_service = StorageService(
            mongo_client=mongo_client,
            minio_client=minio_client,
            db_name=settings.MONGODB_DB_NAME,
            collection_name=settings.MONGODB_DB_COLLECTION,
        )

        # Assign to instance only after all checks pass so fields are always
        # either both-None (pre-init) or both-set (post-init).
        self.mongo_client = mongo_client
        self.minio_client = minio_client
        self.form_processor = FormProcessor(
            storage_service=storage_service,
            mongo_client=self.mongo_client,
        )
        logger.info("✅ Services ready")

    async def _close_services(self) -> None:
        """Close all service connections gracefully."""
        if self.mongo_client is not None:
            await self.mongo_client.close()
        if self.minio_client is not None:
            await self.minio_client.close()

    # ==================== SKIP-EXISTING CHECK ====================

    async def _is_already_processed(self, file_path: Path) -> bool:
        """Return True if the filename already exists in MongoDB."""
        assert self.mongo_client is not None, "_init_services must be called first"
        doc = await self.mongo_client.find_one(
            settings.MONGODB_DB_COLLECTION,
            {"filename": file_path.name},
        )
        return doc is not None

    # ==================== CORE PROCESSING ====================

    async def _process_file(
        self,
        file_path: Path,
        skip_existing: bool = False,
        form_type: Optional[str] = None,
        max_retries: int = 3,
    ) -> UploadResult:
        """
        Process a single file through FormProcessor.process().

        Retries on transient gateway errors, respecting the retryable
        and retry_after fields returned by _call_qwen_api.
        """
        resolved_form_type = form_type or FormProcessor.extract_form_type_from_filename(
            file_path.name
        )
        if not resolved_form_type:
            return UploadResult(
                file_path=file_path,
                success=False,
                error="Cannot detect form type from filename and no --form-type supplied",
            )

        if skip_existing and await self._is_already_processed(file_path):
            logger.info(f"⊘ Skipped: {file_path.name} (already in MongoDB)")
            return UploadResult(
                file_path=file_path,
                success=True,
                skipped=True,
                form_type=resolved_form_type,
            )

        assert self.form_processor is not None, "_init_services must be called first"
        last_error: Optional[str] = None

        for attempt in range(max_retries):
            try:
                result = await self.form_processor.process(
                    image_path=str(file_path),
                    form_type=resolved_form_type,
                    save_to_storage=True,
                )
            except Exception as e:
                last_error = str(e)
                logger.error(f"❌ Exception processing {file_path.name}: {e}", exc_info=True)
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                continue

            if "error" not in result:
                return UploadResult(
                    file_path=file_path,
                    success=True,
                    processing_id=result.get("mongo_id"),
                    status="completed",
                    form_type=resolved_form_type,
                )

            last_error = result.get("error", "unknown error")
            retryable = result.get("retryable", False)

            if retryable and attempt < max_retries - 1:
                # Honour gateway Retry-After if present, else exponential backoff
                delay = result.get("retry_after") or (2 ** attempt)
                logger.warning(
                    f"⚠️  Retryable error for {file_path.name} "
                    f"({last_error}), waiting {delay:.0f}s "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(delay)
                continue

            # Non-retryable or final attempt
            break

        return UploadResult(
            file_path=file_path,
            success=False,
            error=last_error,
            form_type=resolved_form_type,
        )

    # ==================== FILE DISCOVERY ====================

    def _find_image_files(
        self,
        directory: Path,
        recursive: bool = False,
        file_type: Optional[str] = None,
        shuffle: bool = False,
    ) -> List[Path]:
        """
        Find all image files in directory.

        Args:
            directory: Directory to search
            recursive: Whether to search subdirectories
            file_type: Optional file type filter (e.g., 'ITF', 'NAR', 'DSC').
                       If provided, only files with this substring in name followed
                       by an underscore (i.e. "ITF_") with the optional underscore
                       before (i.e. "_ITF_") are returned.
                       Matches patterns: "ITF_", "_ITF_".
            shuffle: Whether to return shuffled list (only applies when file_type
                     is specified). Default: False (returns sorted list)

        Returns:
            List of image file paths, shuffled if file_type is provided and
            shuffle=True, otherwise sorted

        """
        image_extensions = {
            ext if ext.startswith(".") else f".{ext}"
            for ext in ALLOWED_EXTENSIONS
        }

        if not directory.exists():
            raise ValueError(f"Directory not found: {directory}")

        def matches_file_type(filename: str, ft: str) -> bool:
            ft_upper = ft.upper()
            return (
                f"{ft_upper}_" in filename.upper()
                or f"_{ft_upper}_" in filename.upper()
            )

        if file_type is not None:
            candidates = directory.rglob("*") if recursive else directory.glob("*")
            files = [
                f for f in candidates
                if f.is_file()
                and f.suffix.lower() in image_extensions
                and matches_file_type(f.name, file_type)
            ]
        else:
            files = [
                f for f in directory.glob("*")
                if f.is_file() and f.suffix.lower() in image_extensions
            ]

        if shuffle:
            random.shuffle(files)
            return files
        return sorted(files)

    # ==================== BATCH PROCESSING ====================

    async def process_directory(
        self,
        directory: Path,
        recursive: bool = False,
        skip_existing: bool = False,
        form_type: Optional[str] = None,
        concurrency: int = 3,
        max_retries: int = 3,
    ) -> BulkUploadSummary:
        """Process all images in a directory with bounded concurrency."""
        logger.info(f"📁 Processing directory: {directory}")
        logger.info(f"   Recursive: {recursive} | Skip existing: {skip_existing} | "
                    f"Concurrency: {concurrency} | Max retries: {max_retries}")

        files = self._find_image_files(
            directory,
            recursive=recursive,
            file_type=form_type,
            shuffle=True,
        )

        if not files:
            logger.warning(f"⚠️  No image files found in {directory}")
            return BulkUploadSummary(
                total_files=0,
                successful_uploads=0,
                failed_uploads=0,
                skipped_files=0,
                total_processing_time_seconds=0.0,
            )

        logger.info(f"Found {len(files)} image files to process")

        import time
        start_time = time.time()

        semaphore = asyncio.Semaphore(concurrency)
        completed = 0

        async def bounded_process(fp: Path) -> UploadResult:
            nonlocal completed
            async with semaphore:
                res = await self._process_file(
                    fp,
                    skip_existing=skip_existing,
                    form_type=form_type,
                    max_retries=max_retries,
                )
                completed += 1
                _log_file_result(res, completed, len(files))
                return res

        raw = await asyncio.gather(
            *[bounded_process(f) for f in files],
            return_exceptions=True,
        )

        # Normalise any unexpected exceptions returned by gather
        self.results = []
        for item, orig_path in zip(raw, files):
            if isinstance(item, BaseException):
                self.results.append(
                    UploadResult(file_path=orig_path, success=False, error=str(item))
                )
            else:
                self.results.append(item)

        elapsed = time.time() - start_time

        summary = BulkUploadSummary(
            total_files=len(files),
            successful_uploads=sum(1 for r in self.results if r.success and not r.skipped),
            failed_uploads=sum(1 for r in self.results if not r.success),
            skipped_files=sum(1 for r in self.results if r.skipped),
            total_processing_time_seconds=elapsed,
            errors=[str(r.error) for r in self.results if r.error is not None and not r.skipped],
        )

        self._display_summary(summary)
        return summary

    async def process_single_file(
        self,
        file_path: Path,
        form_type: Optional[str] = None,
        max_retries: int = 3,
    ) -> UploadResult:
        """Process a single image file."""
        logger.info(f"📄 Processing file: {file_path}")
        result = await self._process_file(
            file_path,
            form_type=form_type,
            max_retries=max_retries,
        )
        if result.success:
            logger.info(f"✅ File processed (ID: {result.processing_id})")
        else:
            logger.error(f"❌ File failed: {result.error}")
        return result

    # ==================== ENTRY POINT ====================

    async def run(
        self,
        directory: Optional[str],
        file: Optional[str],
        recursive: bool,
        skip_existing: bool,
        form_type: Optional[str],
        concurrency: int,
        max_retries: int,
    ) -> None:
        """Initialise services, run processing, and always close services."""
        await self._init_services()
        try:
            if file:
                await self.process_single_file(
                    file_path=Path(file),
                    form_type=form_type,
                    max_retries=max_retries,
                )
            else:
                assert directory is not None
                await self.process_directory(
                    directory=Path(directory),
                    recursive=recursive,
                    skip_existing=skip_existing,
                    form_type=form_type,
                    concurrency=concurrency,
                    max_retries=max_retries,
                )
        finally:
            await self._close_services()

    # ==================== DISPLAY ====================

    @staticmethod
    def _display_summary(summary: BulkUploadSummary) -> None:
        logger.info("=" * 80)
        logger.info("📊 BULK UPLOAD SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total files processed:  {summary.total_files}")
        logger.info(f"Successful uploads:     {summary.successful_uploads}")
        logger.info(f"Failed uploads:         {summary.failed_uploads}")
        logger.info(f"Skipped files:          {summary.skipped_files}")
        logger.info(f"Total processing time:  {summary.total_processing_time_seconds:.2f}s")

        if summary.failed_uploads > 0:
            logger.warning("⚠️  Failed files:")
            for error in summary.errors:
                logger.warning(f"   - {error}")

        if summary.skipped_files > 0:
            logger.info(f"ℹ️  Skipped {summary.skipped_files} already-processed files")

        logger.info("=" * 80)


# ==================== HELPERS ====================

def _log_file_result(result: UploadResult, idx: int, total: int) -> None:
    prefix = f"[{idx}/{total}] {result.file_path.name}"
    if result.skipped:
        logger.info(f"⊘ {prefix} — skipped")
    elif result.success:
        logger.info(f"✅ {prefix} — ok (ID: {result.processing_id})")
    else:
        logger.error(f"❌ {prefix} — {result.error}")


# ==================== CLI ====================

@click.command()
@click.option(
    "--directory",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Directory containing images to process",
    default=None,
)
@click.option(
    "--file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Single file to process",
    default=None,
)
@click.option("--recursive", is_flag=True, help="Process subdirectories recursively", default=False)
@click.option("--skip-existing", is_flag=True, help="Skip files already in MongoDB", default=False)
@click.option(
    "--form-type",
    type=str,
    help="Override form type detection (ITF, NAR, etc.)",
    default=None,
)
@click.option(
    "--concurrency",
    type=int,
    default=3,
    show_default=True,
    help="Number of files to process in parallel",
)
@click.option(
    "--max-retries",
    type=int,
    default=3,
    show_default=True,
    help="Retry attempts for transient LLM gateway errors",
)
def bulk_upload(
    directory: Optional[str],
    file: Optional[str],
    recursive: bool,
    skip_existing: bool,
    form_type: Optional[str],
    concurrency: int,
    max_retries: int,
) -> None:
    """
    Bulk process form images directly via the LLM gateway.

    Examples:
        # Process entire directory recursively with 5 parallel workers
        python -m backend.cli.bulk_upload --directory ./bridge_images --recursive --concurrency 5

        # Process single file with form type override
        python -m backend.cli.bulk_upload --file ./form_001.png --form-type NAR

        # Process directory, skip files already in MongoDB
        python -m backend.cli.bulk_upload --directory ./bridge_images --skip-existing
    """
    if not directory and not file:
        click.echo("❌ Error: Must provide either --directory or --file")
        sys.exit(1)

    if directory and file:
        click.echo("❌ Error: Cannot provide both --directory and --file")
        sys.exit(1)

    cli = BulkUploadCLI()

    try:
        asyncio.run(
            cli.run(
                directory=directory,
                file=file,
                recursive=recursive,
                skip_existing=skip_existing,
                form_type=form_type,
                concurrency=concurrency,
                max_retries=max_retries,
            )
        )
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    bulk_upload()

# backend/cli/bulk_upload.py
"""
CLI utility for bulk uploading and processing form images via HTTP.

Usage:
    python -m backend.cli.bulk_upload --directory ./bridge_images
    python -m backend.cli.bulk_upload --directory ./bridge_images --recursive
    python -m backend.cli.bulk_upload --directory ./bridge_images --skip-existing
    python -m backend.cli.bulk_upload --file ./bridge_images/form_001.png --form-type ITF
"""

import sys
import json
import click
import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from config.settings import settings

# Configure logging
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    """Result of a single file upload."""
    file_path: Path
    success: bool
    processing_id: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None


@dataclass
class BulkUploadSummary:
    """Summary of bulk upload results."""
    total_files: int
    successful_uploads: int
    failed_uploads: int
    skipped_files: int
    total_processing_time_seconds: float
    errors: List[str]


class BulkUploadCLI:
    """CLI handler for bulk upload operations via HTTP."""

    def __init__(self):
        """Initialize CLI with API endpoint."""
        self.api_url = settings.API_HOST
        self.api_port = settings.API_PORT
        self.results: List[UploadResult] = []

    def _find_image_files(self, directory: Path, recursive: bool = False, ) -> \
    List[Path]:
        """
        Find all image files in directory.

        Args:
            directory: Directory to search
            recursive: Whether to search subdirectories

        Returns:
            List of image file paths
        """
        image_extensions = {
        ext if ext.startswith(".") else f".{ext}"
            for ext in settings.ALLOWED_EXTENSIONS
        }

        if not directory.exists():
            raise ValueError(f"Directory not found: {directory}")

        if recursive:
            files = [f for f in directory.rglob("*") if
                f.is_file() and f.suffix.lower() in image_extensions]
        else:
            files = [f for f in directory.glob("*") if
                f.is_file() and f.suffix.lower() in image_extensions]

        return sorted(files)

    def _upload_file(self, file_path: Path, skip_existing: bool = False,
            form_type: Optional[str] = None, ) -> UploadResult:
        """
        Upload single file via curl.

        Args:
            file_path: Path to image file
            skip_existing: Skip if already uploaded
            form_type: Optional form type override

        Returns:
            UploadResult with success status
        """
        try:
            # Build curl command
            curl_cmd = [
                "curl", "-X", "POST",
                f"https://{self.api_url}:{self.api_port}/api/upload/form",
                "-F",
                f"file=@{file_path}", "-s", "-w", "\n%{http_code}",
            ]

            # Add optional parameters
            if skip_existing:
                curl_cmd.extend(["-F", "skip_existing=true"])
            if form_type:
                curl_cmd.extend(["-F", f"form_type={form_type}"])

            logger.debug(f"Running: {' '.join(curl_cmd)}")

            # Execute curl
            result = subprocess.run(curl_cmd, capture_output=True, text=True,
                timeout=300,  # 5 minute timeout per file
            )

            if result.returncode != 0:
                return UploadResult(file_path=file_path, success=False,
                    error=f"curl failed: {result.stderr}", )

            # Parse response (last line is HTTP status code)
            lines = result.stdout.strip().split("\n")
            if len(lines) < 2:
                return UploadResult(file_path=file_path, success=False,
                    error="Empty response from server", )

            http_code = int(lines[-1])
            response_body = "\n".join(lines[:-1])

            # Handle skip_existing response
            if http_code == 409:  # Conflict - already exists
                logger.info(f"⊘ Skipped: {file_path.name} (already uploaded)")
                return UploadResult(file_path=file_path, success=True,
                    # Don't count as error
                    error="File already exists", )

            # Handle success
            if http_code == 200:
                try:
                    response_json = json.loads(response_body)
                    return UploadResult(file_path=file_path, success=True,
                        processing_id=response_json.get("processing_id"),
                        status=response_json.get("status", "processing"), )
                except json.JSONDecodeError:
                    return UploadResult(file_path=file_path, success=True,
                        error="Could not parse response JSON", )

            # Handle errors
            return UploadResult(file_path=file_path, success=False,
                error=f"HTTP {http_code}: {response_body[:200]}", )

        except subprocess.TimeoutExpired:
            return UploadResult(file_path=file_path, success=False,
                error="Upload timeout (5 minutes)", )
        except Exception as e:
            return UploadResult(file_path=file_path, success=False,
                error=str(e), )

    async def process_directory(self, directory: Path, recursive: bool = False,
            skip_existing: bool = False,
            form_type: Optional[str] = None, ) -> BulkUploadSummary:
        """
        Process all images in a directory.

        Args:
            directory: Directory path
            recursive: Whether to process subdirectories
            skip_existing: Whether to skip existing files
            form_type: Optional form type override

        Returns:
            BulkUploadSummary with results
        """
        logger.info(f"📁 Processing directory: {directory}")
        logger.info(f"   Recursive: {recursive}")
        logger.info(f"   Skip existing: {skip_existing}")
        if form_type:
            logger.info(f"   Form type: {form_type}")

        # Find all image files
        files = self._find_image_files(directory, recursive=recursive)
        if not files:
            logger.warning(f"⚠️  No image files found in {directory}")
            return BulkUploadSummary(total_files=0, successful_uploads=0,
                failed_uploads=0, skipped_files=0,
                total_processing_time_seconds=0.0, errors=[], )

        logger.info(f"Found {len(files)} image files to process")

        # Upload each file
        import time
        start_time = time.time()

        for idx, file_path in enumerate(files, 1):
            logger.info(f"[{idx}/{len(files)}] Uploading: {file_path.name}")
            result = self._upload_file(file_path=file_path,
                skip_existing=skip_existing, form_type=form_type, )
            self.results.append(result)

            if result.success:
                if result.error and "already exists" in result.error:
                    pass  # Already logged as skipped
                else:
                    logger.info(f"   ✅ Success (ID: {result.processing_id})")
            else:
                logger.error(f"   ❌ Failed: {result.error}")

        elapsed = time.time() - start_time

        # Calculate summary
        successful = sum(1 for r in self.results if r.success and not r.error)
        failed = sum(1 for r in self.results if not r.success)
        skipped = sum(
            1 for r in self.results if r.error and "already exists" in r.error)

        summary = BulkUploadSummary(total_files=len(files),
            successful_uploads=successful, failed_uploads=failed,
            skipped_files=skipped, total_processing_time_seconds=elapsed,
            errors=[r.error for r in self.results if
                    r.error and "already exists" not in r.error], )

        self._display_summary(summary)
        return summary

    async def process_single_file(self, file_path: Path,
            form_type: Optional[str] = None, ) -> UploadResult:
        """
        Process a single image file.

        Args:
            file_path: File path
            form_type: Optional form type override

        Returns:
            UploadResult
        """
        logger.info(f"📄 Processing file: {file_path}")
        if form_type:
            logger.info(f"   Form type: {form_type}")

        result = self._upload_file(file_path=file_path, form_type=form_type, )

        if result.success:
            logger.info(f"✅ File processed successfully")
            logger.info(f"   Processing ID: {result.processing_id}")
            logger.info(f"   Status: {result.status}")
        else:
            logger.error(f"❌ File processing failed: {result.error}")

        return result

    @staticmethod
    def _display_summary(summary: BulkUploadSummary) -> None:
        """
        Display bulk upload summary.

        Args:
            summary: BulkUploadSummary object
        """
        logger.info("=" * 80)
        logger.info("📊 BULK UPLOAD SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total files processed: {summary.total_files}")
        logger.info(f"Successful uploads: {summary.successful_uploads}")
        logger.info(f"Failed uploads: {summary.failed_uploads}")
        logger.info(f"Skipped files: {summary.skipped_files}")
        logger.info(
            f"Total processing time: {summary.total_processing_time_seconds:.2f}s")

        if summary.failed_uploads > 0:
            logger.warning("⚠️  Failed files:")
            for error in summary.errors:
                logger.warning(f"   - {error}")

        if summary.skipped_files > 0:
            logger.info(f"ℹ️  Skipped {summary.skipped_files} existing files")

        logger.info("=" * 80)


@click.command()
@click.option("--directory",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Directory containing images to process", default=None, )
@click.option("--file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Single file to process", default=None, )
@click.option("--recursive", is_flag=True,
    help="Process subdirectories recursively", default=False, )
@click.option("--skip-existing", is_flag=True,
    help="Skip files that already exist", default=False, )
@click.option("--form-type", type=str,
    help="Override form type detection (ITF, NAR, etc.)", default=None, )
def bulk_upload(
        directory: Optional[str],
        file: Optional[str],
        recursive: bool,
        skip_existing: bool,
        form_type: Optional[str],
) -> None:
    """
    Bulk upload and process form images via HTTP API.

    Examples:
        # Process entire directory recursively
        python -m backend.cli.bulk_upload --directory ./bridge_images --recursive

        # Process single file with form type override
        python -m backend.cli.bulk_upload --file ./bridge_images/form_001.png --form-type ITF

        # Process directory, skip existing files
        python -m backend.cli.bulk_upload --directory ./bridge_images --skip-existing

        # Process with custom API endpoint
        python -m backend.cli.bulk_upload --directory ./bridge_images
    """

    # Validate arguments
    if not directory and not file:
        click.echo("❌ Error: Must provide either --directory or --file")
        sys.exit(1)

    if directory and file:
        click.echo("❌ Error: Cannot provide both --directory and --file")
        sys.exit(1)

    cli = BulkUploadCLI()

    try:
        if file:
            # Process single file
            asyncio.run(cli.process_single_file(file_path=Path(file),
                form_type=form_type, ))
        else:
            # Process directory
            asyncio.run(cli.process_directory(directory=Path(directory),
                recursive=recursive, skip_existing=skip_existing,
                form_type=form_type, ))

    except KeyboardInterrupt:
        logger.warning("\n⚠️  Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    bulk_upload()

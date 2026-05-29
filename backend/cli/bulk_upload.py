# backend/cli/bulk_upload.py
"""
CLI utility for bulk uploading and processing form images.

Usage:
    python -m backend.cli.bulk_upload --directory ./bridge_images
    python -m backend.cli.bulk_upload --directory ./bridge_images --recursive
    python -m backend.cli.bulk_upload --directory ./bridge_images --skip-existing
    python -m backend.cli.bulk_upload --file ./bridge_images/form_001.png --form-type ITF
"""

import sys
import asyncio
import logging
from pathlib import Path
from typing import Optional

import click

# ✅ CRITICAL: Add backend directory to path for imports
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# ✅ NOW imports will work
from config.settings import settings
from clients.mongo_client import MongoClient
from clients.minio_client import MinIOClient
from services.storage_service import StorageService
from services.form_processor import FormProcessor
from services.bulk_upload_service import BulkUploadService


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class BulkUploadCLI:
    """CLI handler for bulk upload operations."""

    def __init__(self):
        """Initialize CLI with services."""
        self.mongo_client: Optional[MongoClient] = None
        self.minio_client: Optional[MinIOClient] = None
        self.storage_service: Optional[StorageService] = None
        self.form_processor: Optional[FormProcessor] = None
        self.bulk_upload_service: Optional[BulkUploadService] = None

    async def initialize(self) -> bool:
        """
        Initialize all services.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info("🚀 Initializing services for bulk upload...")

            # ==================== MONGODB ====================
            logger.info("🗄️  Connecting to MongoDB...")
            try:
                mongo_uri = settings.get_mongodb_uri()
                self.mongo_client = MongoClient(
                    uri=mongo_uri,
                    db_name=settings.MONGODB_DB_NAME,
                )

                health_check = await self.mongo_client.health_check()
                if not health_check["connected"]:
                    raise Exception(f"Health check failed: {health_check.get('error')}")

                logger.info(f"✅ MongoDB connected: {settings.MONGODB_DB_NAME}")

            except Exception as e:
                logger.error(f"❌ MongoDB initialization failed: {e}")
                return False

            # ==================== MINIO ====================
            logger.info("🪣 Connecting to MinIO...")
            try:
                minio_config = settings.get_minio_config()
                self.minio_client = MinIOClient(
                    endpoint=minio_config["endpoint"],
                    access_key=minio_config["access_key"],
                    secret_key=minio_config["secret_key"],
                    bucket_name=minio_config["bucket_name"],
                    secure=minio_config["secure"],
                    region=minio_config["region"],
                )

                # Test connectivity
                try:
                    self.minio_client.client.list_buckets()
                except Exception as e:
                    raise Exception(f"MinIO connectivity test failed: {e}")

                await self.minio_client.ensure_bucket_exists()
                logger.info(f"✅ MinIO connected: {minio_config['bucket_name']}")

            except Exception as e:
                logger.error(f"❌ MinIO initialization failed: {e}")
                return False

            # ==================== SERVICES ====================
            logger.info("🔧 Initializing services...")
            try:
                self.storage_service = StorageService(
                    mongo_client=self.mongo_client,
                    minio_client=self.minio_client,
                    db_name=settings.MONGODB_DB_NAME,
                    collection_name=settings.MONGODB_DB_COLLECTION,
                )

                self.form_processor = FormProcessor(
                    storage_service=self.storage_service,
                    mongo_client=self.mongo_client,
                )

                self.bulk_upload_service = BulkUploadService(
                    form_processor=self.form_processor,
                    storage_service=self.storage_service,
                )

                logger.info("✅ All services initialized")

            except Exception as e:
                logger.error(f"❌ Service initialization failed: {e}")
                return False

            return True

        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}", exc_info=True)
            return False

    async def cleanup(self):
        """Clean up resources."""
        try:
            if self.minio_client is not None:
                await self.minio_client.close()
                logger.info("✅ MinIO closed")

            if self.mongo_client is not None:
                await self.mongo_client.close()
                logger.info("✅ MongoDB closed")

        except Exception as e:
            logger.error(f"⚠️  Cleanup error: {e}")

    async def process_directory(
        self,
        directory: Path,
        recursive: bool = False,
        skip_existing: bool = False,
        form_type: Optional[str] = None,
    ) -> None:
        """
        Process all images in a directory.

        Args:
            directory: Directory path
            recursive: Whether to process subdirectories
            skip_existing: Whether to skip existing files
            form_type: Optional form type override
        """
        if not await self.initialize():
            logger.error("❌ Failed to initialize services")
            return

        try:
            logger.info(f"📁 Processing directory: {directory}")
            logger.info(f"   Recursive: {recursive}")
            logger.info(f"   Skip existing: {skip_existing}")
            if form_type:
                logger.info(f"   Form type: {form_type}")

            result = await self.bulk_upload_service.process_directory(
                directory_path=directory,
                recursive=recursive,
                skip_existing=skip_existing,
                form_type_override=form_type,
            )

            # ✅ Display results
            self._display_summary(result)

        except Exception as e:
            logger.error(f"❌ Processing failed: {e}", exc_info=True)

        finally:
            await self.cleanup()

    async def process_single_file(
        self,
        file_path: Path,
        form_type: Optional[str] = None,
    ) -> None:
        """
        Process a single image file.

        Args:
            file_path: File path
            form_type: Optional form type override
        """
        if not await self.initialize():
            logger.error("❌ Failed to initialize services")
            return

        try:
            logger.info(f"📄 Processing file: {file_path}")
            if form_type:
                logger.info(f"   Form type: {form_type}")

            result = await self.bulk_upload_service.process_single_file(
                file_path=file_path,
                form_type_override=form_type,
            )

            # ✅ Display result
            if result.success:
                logger.info(f"✅ File processed successfully")
                logger.info(f"   Processing ID: {result.processing_id}")
                logger.info(f"   Form type: {result.form_type}")
                logger.info(f"   Status: {result.status}")
            else:
                logger.error(f"❌ File processing failed: {result.error}")

        except Exception as e:
            logger.error(f"❌ Processing failed: {e}", exc_info=True)

        finally:
            await self.cleanup()

    @staticmethod
    def _display_summary(summary) -> None:
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
        logger.info(f"Total processing time: {summary.total_processing_time_seconds:.2f}s")

        if summary.failed_uploads > 0:
            logger.warning("⚠️  Failed files:")
            for error in summary.errors:
                logger.warning(f"   - {error}")

        if summary.skipped_files > 0:
            logger.info(f"ℹ️  Skipped {summary.skipped_files} existing files")

        logger.info("=" * 80)


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
@click.option(
    "--recursive",
    is_flag=True,
    help="Process subdirectories recursively",
    default=False,
)
@click.option(
    "--skip-existing",
    is_flag=True,
    help="Skip files that already exist in MongoDB",
    default=False,
)
@click.option(
    "--form-type",
    type=str,
    help="Override form type detection (ITF, NAR, etc.)",
    default=None,
)
def bulk_upload(
    directory: Optional[str],
    file: Optional[str],
    recursive: bool,
    skip_existing: bool,
    form_type: Optional[str],
) -> None:
    """
    Bulk upload and process form images.

    Examples:
        # Process entire directory recursively
        python -m backend.cli.bulk_upload --directory ./bridge_images --recursive

        # Process single file with form type override
        python -m backend.cli.bulk_upload --file ./bridge_images/form_001.png --form-type ITF

        # Process directory, skip existing files
        python -m backend.cli.bulk_upload --directory ./bridge_images --skip-existing
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
            asyncio.run(
                cli.process_single_file(
                    file_path=Path(file),
                    form_type=form_type,
                )
            )
        else:
            # Process directory
            asyncio.run(
                cli.process_directory(
                    directory=Path(directory),
                    recursive=recursive,
                    skip_existing=skip_existing,
                    form_type=form_type,
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

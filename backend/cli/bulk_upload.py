# backend/cli/bulk_upload.py
"""
CLI utility for bulk uploading forms from a directory.

Usage:
    python -m backend.cli.bulk_upload --directory /path/to/forms
    python -m backend.cli.bulk_upload --directory /path/to/forms --form-type ITF --recursive
    python -m backend.cli.bulk_upload --directory /path/to/forms --skip-existing
"""

import asyncio
import logging
from typing import Optional
import click
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@click.command()
@click.option(
    '--directory',
    '-d',
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help='Directory containing forms to upload'
)
@click.option(
    '--form-type',
    '-t',
    default=None,
    help='Form type (ITF, NAR, etc.). Auto-detect if not specified'
)
@click.option(
    '--case-id',
    '-c',
    default=None,
    help='Case ID for all files'
)
@click.option(
    '--recursive',
    '-r',
    is_flag=True,
    help='Process subdirectories recursively'
)
@click.option(
    '--skip-existing',
    '-s',
    is_flag=True,
    help='Skip files already in database'
)
@click.option(
    '--with-agent',
    is_flag=True,
    default=True,
    help='Use form agent for processing (default: True)'
)
@click.option(
    '--no-agent',
    is_flag=True,
    help='Disable form agent processing'
)
def bulk_upload(
        directory: str,
        form_type: Optional[str],
        case_id: Optional[str],
        recursive: bool,
        skip_existing: bool,
        with_agent: bool,
        no_agent: bool,
) -> None:
    """
    Bulk upload forms from a directory.

    Example:
        python -m backend.cli.bulk_upload --directory ./forms --recursive --with-agent
    """
    from config.settings import settings
    from clients.mongo_client import MongoClient
    from clients.minio_client import MinIOClient
    from services.storage_service import StorageService
    from services.form_processor import FormProcessor
    from services.bulk_upload_service import BulkUploadService

    # Determine agent usage
    use_agent = with_agent and not no_agent

    logger.info(f"🚀 Starting bulk upload from: {directory}")
    logger.info(f"   Form Type: {form_type or 'auto-detect'}")
    logger.info(f"   Case ID: {case_id or 'not set'}")
    logger.info(f"   Recursive: {recursive}")
    logger.info(f"   Skip Existing: {skip_existing}")
    logger.info(f"   Use Agent: {use_agent}")

    # Initialize clients and services
    try:
        # ==================== INITIALIZE CLIENTS ====================
        logger.info("🔧 Initializing clients...")

        mongo_client = MongoClient(
            connection_string=settings.MONGODB_CONNECTION_STRING,
            db_name=settings.MONGODB_DB_NAME,
        )

        minio_client = MinIOClient(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            bucket_name=settings.MINIO_BUCKET_NAME,
            use_ssl=settings.MINIO_USE_SSL,
        )

        storage_service = StorageService(
            mongo_client=mongo_client,
            minio_client=minio_client,
        )

        form_processor = FormProcessor(
            storage_service=storage_service,
            llm_provider=settings.LLM_PROVIDER,
        )

        bulk_upload_service = BulkUploadService(
            form_processor=form_processor,
            storage_service=storage_service,
        )

        logger.info("✅ Clients initialized successfully")

        # ==================== RUN BULK UPLOAD ====================
        summary = asyncio.run(
            bulk_upload_service.process_directory(
                directory_path=directory,
                form_type=form_type,
                case_id=case_id,
                recursive=recursive,
                process_with_agent=use_agent,
                skip_existing=skip_existing,
            )
        )

        # ==================== PRINT RESULTS ====================
        bulk_upload_service.print_summary(summary)

        # ==================== EXIT WITH APPROPRIATE CODE ====================
        if summary.failed > 0:
            sys.exit(1)
        else:
            sys.exit(0)

    except Exception as e:
        logger.error(f"❌ Bulk upload failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    bulk_upload()

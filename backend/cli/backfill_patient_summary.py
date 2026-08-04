# backend/cli/backfill_patient_summary.py
"""
One-off backfill: populates `patient_summary` from every document already
in the parent form-results collection (settings.MONGODB_DB_COLLECTION).

The change stream watcher (services/change_stream_service.py) only sees
events that occur *after* it starts, so this script must be run once to
cover pre-existing history - and again any time the watcher's resume token
is dropped (e.g. after prolonged downtime past the oplog retention window).

Usage:
    python -m cli.backfill_patient_summary
    python -m cli.backfill_patient_summary --batch-size 200
"""

import asyncio
import logging

import click

from config.settings import settings
from clients.mongo_client import MongoClient
from services.patient_summary_service import PatientSummaryService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def run_backfill(batch_size: int) -> None:
    mongo_client = MongoClient(
        uri=settings.get_mongodb_uri(),
        db_name=settings.MONGODB_DB_NAME,
    )

    try:
        health = await mongo_client.health_check()
        if not health["connected"]:
            raise RuntimeError(f"Could not connect to MongoDB: {health.get('error')}")

        patient_summary_service = PatientSummaryService(
            mongo_client=mongo_client,
            db_name=settings.MONGODB_DB_NAME,
            collection_name=settings.MONGODB_PATIENT_SUMMARY_COLLECTION,
        )

        source_collection = mongo_client.client[settings.MONGODB_DB_NAME][
            settings.MONGODB_DB_COLLECTION
        ]

        total = await source_collection.count_documents({})
        logger.info(f"📦 Backfilling patient_summary from {total} source document(s)...")

        processed = 0
        merged = 0
        skipped = 0

        cursor = source_collection.find({}).sort("created_at", 1).batch_size(batch_size)
        async for doc in cursor:
            processed += 1
            patient_id = await patient_summary_service.upsert_from_document(doc)
            if patient_id:
                merged += 1
            else:
                skipped += 1

            if processed % batch_size == 0:
                logger.info(f"   ...{processed}/{total} processed ({merged} merged, {skipped} skipped)")

        logger.info(
            f"✅ Backfill complete: {processed} processed, {merged} merged, {skipped} skipped"
        )

    finally:
        await mongo_client.close()


@click.command()
@click.option(
    "--batch-size",
    type=int,
    default=100,
    help="Number of source documents to fetch per batch / progress log interval",
)
def backfill(batch_size: int):
    """Populate patient_summary from existing form-results history."""
    asyncio.run(run_backfill(batch_size))


if __name__ == "__main__":
    backfill()

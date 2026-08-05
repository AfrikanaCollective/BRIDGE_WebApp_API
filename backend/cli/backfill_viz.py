# backend/cli/backfill_viz.py
"""
One-off backfill: populates `patient_summary_viz` from every document already
in `patient_summary`, applying the visualisation key-rename map.

The viz change stream watcher (services/viz_sync_service.py) only sees events
that occur *after* it starts, so this script must be run once to cover
pre-existing history - and again any time the watcher's resume token is dropped
(e.g. after prolonged downtime past the oplog retention window).

Usage:
    python -m cli.backfill_viz
    python -m cli.backfill_viz --batch-size 200
"""

import asyncio
import logging

import click

from config.settings import settings
from clients.mongo_client import MongoClient
from services.viz_sync_service import VizSyncService

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

        viz_sync_service = VizSyncService(
            mongo_client=mongo_client,
            db_name=settings.MONGODB_DB_NAME,
            collection_name=settings.MONGODB_VIZ_COLLECTION,
        )

        counts = await viz_sync_service.backfill_all(
            source_collection_name=settings.MONGODB_PATIENT_SUMMARY_COLLECTION,
            batch_size=batch_size,
        )

        logger.info(
            f"✅ Viz backfill complete: "
            f"{counts['processed']} processed, "
            f"{counts['merged']} merged, "
            f"{counts['skipped']} skipped"
        )

    finally:
        await mongo_client.close()


@click.command()
@click.option(
    "--batch-size",
    type=int,
    default=100,
    help="Number of patient_summary documents to process per batch / progress log interval",
)
def backfill(batch_size: int):
    """Populate patient_summary_viz from existing patient_summary history."""
    asyncio.run(run_backfill(batch_size))


if __name__ == "__main__":
    backfill()

# backend/services/change_stream_service.py
"""
Watches the parent form-results collection via a MongoDB change stream and
keeps `patient_summary` in sync in near-real-time.

Requires MongoDB to run as a replica set (or sharded cluster) - change
streams are not available against a standalone mongod.
"""

import asyncio
import logging
from typing import Optional

from pymongo.errors import PyMongoError

from clients.mongo_client import MongoClient
from config.settings import settings
from services.patient_summary_service import PatientSummaryService

logger = logging.getLogger(__name__)

_STATE_DOC_ID = "patient_summary_sync"
_INITIAL_RECONNECT_BACKOFF_SECONDS = 5
_MAX_RECONNECT_BACKOFF_SECONDS = 60


class ChangeStreamWatcher:
    """
    Streams insert/update/replace events from the parent collection and
    merges each changed document into `patient_summary` via
    PatientSummaryService. The resume token is persisted after every
    processed event so a restart resumes instead of replaying or dropping
    events.
    """

    def __init__(
            self,
            mongo_client: MongoClient,
            patient_summary_service: PatientSummaryService,
            db_name: str = settings.MONGODB_DB_NAME,
            source_collection_name: str = settings.MONGODB_DB_COLLECTION,
            state_collection_name: str = settings.MONGODB_CHANGE_STREAM_STATE_COLLECTION,
    ):
        self.mongo = mongo_client
        self.patient_summary_service = patient_summary_service
        self.db_name = db_name
        self.source_collection_name = source_collection_name
        self.state_collection_name = state_collection_name
        self._stopped = asyncio.Event()

        logger.info(
            f"👁️  ChangeStreamWatcher initialized: watching "
            f"{db_name}.{source_collection_name} -> {settings.MONGODB_PATIENT_SUMMARY_COLLECTION}"
        )

    @property
    def source_collection(self):
        return self.mongo.client[self.db_name][self.source_collection_name]

    @property
    def state_collection(self):
        return self.mongo.client[self.db_name][self.state_collection_name]

    async def _get_resume_token(self) -> Optional[dict]:
        state_doc = await self.state_collection.find_one({"_id": _STATE_DOC_ID})
        return state_doc.get("resume_token") if state_doc else None

    async def _save_resume_token(self, resume_token: dict) -> None:
        await self.state_collection.update_one(
            {"_id": _STATE_DOC_ID},
            {"$set": {"resume_token": resume_token}},
            upsert=True,
        )

    def stop(self) -> None:
        """Signal the watch loop to exit after the current event."""
        self._stopped.set()

    async def run(self) -> None:
        """
        Main watch loop. Reconnects with exponential backoff on transient
        errors. If the resume token is no longer valid (e.g. oplog history
        was lost while disconnected), drops it and resumes from "now" -
        re-run cli/backfill_patient_summary.py afterwards to repair any gap.
        """
        logger.info(
            f"👁️  Starting change stream watcher on "
            f"{self.db_name}.{self.source_collection_name}"
        )
        backoff = _INITIAL_RECONNECT_BACKOFF_SECONDS

        while not self._stopped.is_set():
            resume_token = await self._get_resume_token()
            pipeline = [
                {"$match": {"operationType": {"$in": ["insert", "update", "replace", "delete"]}}}
            ]
            try:
                stream = await self.source_collection.watch(
                    pipeline=pipeline,
                    full_document="updateLookup",
                    resume_after=resume_token,
                )
                async with stream:
                    backoff = _INITIAL_RECONNECT_BACKOFF_SECONDS  # reset after a clean connect
                    async for change in stream:
                        if self._stopped.is_set():
                            break

                        op = change.get("operationType")
                        full_document = change.get("fullDocument")
                        if op == "delete":
                            # fullDocument is unavailable for deletes; the history
                            # route already cascaded the removal to patient_summary
                            # synchronously before this event fires.
                            logger.info(
                                f"🗑️  form-results delete event received "
                                f"(documentKey={change.get('documentKey')}); "
                                f"patient_summary cascade handled by history route"
                            )
                        elif full_document:
                            try:
                                await self.patient_summary_service.upsert_from_document(
                                    full_document
                                )
                            except Exception as e:
                                logger.error(
                                    f"❌ Failed to merge change into patient_summary: {e}",
                                    exc_info=True,
                                )

                        await self._save_resume_token(change["_id"])

            except asyncio.CancelledError:
                logger.info("🛑 Change stream watcher cancelled")
                raise

            except PyMongoError as e:
                error_text = str(e)
                if "ChangeStreamHistoryLost" in error_text or "resume point" in error_text.lower():
                    logger.warning(
                        f"⚠️  Change stream resume token invalid, restarting from now "
                        f"(re-run cli/backfill_patient_summary.py to repair any gap): {e}"
                    )
                    await self.state_collection.delete_one({"_id": _STATE_DOC_ID})
                else:
                    logger.error(f"❌ Change stream error, reconnecting: {e}", exc_info=True)

                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _MAX_RECONNECT_BACKOFF_SECONDS)

            except Exception as e:
                logger.error(f"❌ Unexpected change stream error, reconnecting: {e}", exc_info=True)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _MAX_RECONNECT_BACKOFF_SECONDS)

        logger.info("🛑 Change stream watcher stopped")

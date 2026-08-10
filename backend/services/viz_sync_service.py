# backend/services/viz_sync_service.py
"""
Watches `patient_summary` via a MongoDB change stream and keeps
`patient_summary_viz` in sync with visualisation-friendly short key names.

VizSyncService handles the document transformation.
VizStreamWatcher runs the change stream loop and calls VizSyncService on
each event.  The resume token is persisted after every processed event so a
restart resumes without replaying or dropping events.

Requires MongoDB to run as a replica set (change streams are not available
against a standalone mongod).
"""

import asyncio
import logging
import re
from typing import Any, Dict, Optional

from pymongo.errors import PyMongoError

from clients.mongo_client import MongoClient
from config.settings import settings
from utils.viz_key_map import (
    INVERTED_VIZ_KEY_MAP,
    NUMERIC_VIZ_KEYS,
    BOOLEAN_VIZ_KEYS,
    DIAGNOSIS_VIZ_KEYS,
    CAPILLARY_REFILL_VIZ_KEYS,
    CHEST_INDRAWING_VIZ_KEYS,
    ANTIBIOTICS_SCAN_EXCLUDE_KEYS,
)

logger = logging.getLogger(__name__)

_VIZ_STATE_DOC_ID = "patient_summary_viz_sync"
_INITIAL_RECONNECT_BACKOFF_SECONDS = 5
_MAX_RECONNECT_BACKOFF_SECONDS = 60

_METADATA_FIELDS = {"created_at", "updated_at"}


_TRUTHY_STRINGS: frozenset[str] = frozenset({"Positive", "Y", "Yes", "True"})
_FALSY_STRINGS: frozenset[str] = frozenset({"Negative", "N", "No", "False"})


def _to_bool(value):
    """
    Recode clinical boolean-like strings to Python bool.
    'Positive'/'Y'/'Yes'/'True' → True
    'Negative'/'N'/'No'/'False' → False
    Any other value (e.g. 'Unknown', None, actual bool) passes through unchanged.
    """
    if value in _TRUTHY_STRINGS:
        return True
    if value in _FALSY_STRINGS:
        return False
    return value


def _to_diagnosis_bool(value):
    """
    Recode diagnosis field values to bool.
    Any non-null value other than 'N' → True.
    'N' and None pass through unchanged.
    """
    if value is None or value == "N":
        return value
    return True


_CAPILLARY_REFILL_MAX = 7
_CAPILLARY_REFILL_RE = re.compile(r"\d+(?:\.\d+)?")


def _to_capillary_refill(value):
    """
    Extract the first number from a capillary refill value (which may be an
    embedded string such as '2 seconds' or '3-4').  Whole-number results are
    stored as int; values with a decimal part as float.
    Returns None if no number can be parsed or the extracted value exceeds
    _CAPILLARY_REFILL_MAX seconds.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        n = float(value)
    else:
        match = _CAPILLARY_REFILL_RE.search(str(value))
        if not match:
            return None
        n = float(match.group())
    if n > _CAPILLARY_REFILL_MAX:
        return None
    return int(n) if n == int(n) else n


def _to_chest_indrawing_bool(value):
    """
    Recode chest_indrawing to bool.
    True when the value is not null and is either 'Severe' or True.
    Everything else ('Mild', 'mild', 'None', False, null) → False.
    """
    if value is None:
        return False
    return value == "Severe" or value is True


def _to_numeric(value):
    """
    Coerce a value to int or float.
    Whole-number results (e.g. 36.0, '150') are returned as int.
    Values that cannot be converted are returned unchanged.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value == int(value) else value
    try:
        f = float(value)
        return int(f) if f == int(f) else f
    except (ValueError, TypeError):
        return value


_SKIP_SCAN_KEYS = {"_id"} | _METADATA_FIELDS


def _has_sepsis(flat_doc: Dict[str, Any]) -> bool:
    """
    Return True if any clinical key or string value in the flat viz document
    contains the word 'sepsis' (case-insensitive).
    _id and metadata fields are excluded from the scan.
    """
    for key, value in flat_doc.items():
        if key in _SKIP_SCAN_KEYS:
            continue
        if "sepsis" in key.lower():
            return True
        if isinstance(value, str) and "sepsis" in value.lower():
            return True
    return False


_SKIP_ANTIBIOTICS_KEYS = _SKIP_SCAN_KEYS | ANTIBIOTICS_SCAN_EXCLUDE_KEYS


def _has_antibiotics(flat_doc: Dict[str, Any]) -> bool:
    """
    Return True if any clinical key or string value in the flat viz document
    contains the word 'antibiotics' (case-insensitive).
    _id, metadata fields, and ANTIBIOTICS_SCAN_EXCLUDE_KEYS are excluded.
    """
    for key, value in flat_doc.items():
        if key in _SKIP_ANTIBIOTICS_KEYS:
            continue
        if "antibiotics" in key.lower():
            return True
        if isinstance(value, str) and "antibiotics" in value.lower():
            return True
    return False


class VizSyncService:
    """
    Transforms a patient_summary document into its visualisation form
    (short key names) and writes it to patient_summary_viz.
    """

    def __init__(
            self,
            mongo_client: MongoClient,
            db_name: str = settings.MONGODB_DB_NAME,
            collection_name: str = settings.MONGODB_VIZ_COLLECTION,
    ):
        self.mongo = mongo_client
        self.db_name = db_name
        self.collection_name = collection_name

        logger.info(
            f"📊 VizSyncService initialized: MongoDB({db_name}.{collection_name})"
        )

    @property
    def collection(self):
        return self.mongo.client[self.db_name][self.collection_name]

    def remap_document(self, patient_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return a flat document with all ITF/NAR leaf fields merged and renamed.

        ITF fields are written first; NAR fields overwrite any shared key so
        that the more-detailed admission record wins on collision.  Fields not
        present in the key map are kept under their original name.  Metadata
        fields (created_at, updated_at) and _id are copied verbatim and are
        never overwritten by form data.
        """
        flat: Dict[str, Any] = {}

        for form_type in ("ITF", "NAR"):
            inv_map = INVERTED_VIZ_KEY_MAP.get(form_type, {})
            form_data = patient_doc.get(form_type)
            if not isinstance(form_data, dict):
                continue
            for field, value in form_data.items():
                viz_key = inv_map.get(field, field)
                if viz_key in NUMERIC_VIZ_KEYS:
                    value = _to_numeric(value)
                elif viz_key in CAPILLARY_REFILL_VIZ_KEYS:
                    value = _to_capillary_refill(value)
                elif viz_key in CHEST_INDRAWING_VIZ_KEYS:
                    value = _to_chest_indrawing_bool(value)
                elif viz_key in BOOLEAN_VIZ_KEYS:
                    value = _to_bool(value)
                elif viz_key in DIAGNOSIS_VIZ_KEYS:
                    value = _to_diagnosis_bool(value)
                flat[viz_key] = value

        viz_doc: Dict[str, Any] = {"_id": patient_doc["_id"]}
        viz_doc.update(flat)
        viz_doc["has_sepsis"] = _has_sepsis(flat)
        viz_doc["infection_antibiotics"] = _has_antibiotics(flat)

        for field in _METADATA_FIELDS:
            if field in patient_doc:
                viz_doc[field] = patient_doc[field]

        return viz_doc

    async def upsert_from_patient_summary(
            self, patient_doc: Dict[str, Any]
    ) -> Optional[str]:
        """
        Remap a patient_summary document and upsert it into patient_summary_viz.
        Returns the patient _id on success, None if the document was skipped.
        """
        patient_id = patient_doc.get("_id")
        if not patient_id:
            logger.debug("⏭️  Skipping viz upsert: document has no _id")
            return None

        has_form_data = any(
            isinstance(patient_doc.get(ft), dict)
            for ft in INVERTED_VIZ_KEY_MAP
        )
        if not has_form_data:
            logger.debug(
                f"⏭️  Skipping viz upsert for {patient_id!r}: no ITF/NAR data"
            )
            return None

        viz_doc = self.remap_document(patient_doc)

        await self.collection.replace_one(
            {"_id": patient_id},
            viz_doc,
            upsert=True,
        )

        field_count = len(viz_doc) - len(_METADATA_FIELDS & viz_doc.keys()) - 1  # exclude _id
        logger.info(
            f"✅ Viz upsert: patient_id={patient_id!r}  {field_count} flat field(s)"
        )
        return str(patient_id)

    async def backfill_all(
            self,
            source_collection_name: str = settings.MONGODB_PATIENT_SUMMARY_COLLECTION,
            batch_size: int = 100,
    ) -> Dict[str, int]:
        """
        Process all existing patient_summary documents into patient_summary_viz.
        Useful after first deployment or after a resume-token gap.
        """
        source = self.mongo.client[self.db_name][source_collection_name]
        total = await source.count_documents({})
        logger.info(f"📦 Viz backfill: processing {total} patient_summary document(s)...")

        processed = merged = skipped = 0
        async for doc in source.find({}).sort("_id", 1).batch_size(batch_size):
            processed += 1
            patient_id = await self.upsert_from_patient_summary(doc)
            if patient_id:
                merged += 1
            else:
                skipped += 1
            if processed % batch_size == 0:
                logger.info(
                    f"   ...{processed}/{total} processed "
                    f"({merged} merged, {skipped} skipped)"
                )

        logger.info(
            f"✅ Viz backfill complete: {processed} processed, "
            f"{merged} merged, {skipped} skipped"
        )
        return {"processed": processed, "merged": merged, "skipped": skipped}


class VizStreamWatcher:
    """
    Streams insert/update/replace events from `patient_summary` and keeps
    `patient_summary_viz` in sync via VizSyncService.  The resume token is
    persisted after every processed event.
    """

    def __init__(
            self,
            mongo_client: MongoClient,
            viz_sync_service: VizSyncService,
            db_name: str = settings.MONGODB_DB_NAME,
            source_collection_name: str = settings.MONGODB_PATIENT_SUMMARY_COLLECTION,
            state_collection_name: str = settings.MONGODB_VIZ_STREAM_STATE_COLLECTION,
    ):
        self.mongo = mongo_client
        self.viz_sync_service = viz_sync_service
        self.db_name = db_name
        self.source_collection_name = source_collection_name
        self.state_collection_name = state_collection_name
        self._stopped = asyncio.Event()

        logger.info(
            f"📊 VizStreamWatcher initialized: watching "
            f"{db_name}.{source_collection_name} → "
            f"{settings.MONGODB_VIZ_COLLECTION}"
        )

    @property
    def source_collection(self):
        return self.mongo.client[self.db_name][self.source_collection_name]

    @property
    def state_collection(self):
        return self.mongo.client[self.db_name][self.state_collection_name]

    async def _get_resume_token(self) -> Optional[dict]:
        state_doc = await self.state_collection.find_one({"_id": _VIZ_STATE_DOC_ID})
        return state_doc.get("resume_token") if state_doc else None

    async def _save_resume_token(self, resume_token: dict) -> None:
        await self.state_collection.update_one(
            {"_id": _VIZ_STATE_DOC_ID},
            {"$set": {"resume_token": resume_token}},
            upsert=True,
        )

    def stop(self) -> None:
        self._stopped.set()

    async def run(self) -> None:
        """
        Main watch loop.  Reconnects with exponential backoff on transient
        errors.  Drops stale resume tokens rather than crashing.
        """
        logger.info(
            f"📊 Starting viz change stream watcher on "
            f"{self.db_name}.{self.source_collection_name}"
        )
        backoff = _INITIAL_RECONNECT_BACKOFF_SECONDS

        while not self._stopped.is_set():
            resume_token = await self._get_resume_token()
            pipeline = [
                {"$match": {"operationType": {"$in": ["insert", "update", "replace"]}}}
            ]
            try:
                stream = await self.source_collection.watch(
                    pipeline=pipeline,
                    full_document="updateLookup",
                    resume_after=resume_token,
                )
                async with stream:
                    backoff = _INITIAL_RECONNECT_BACKOFF_SECONDS
                    async for change in stream:
                        if self._stopped.is_set():
                            break

                        full_document = change.get("fullDocument")
                        if full_document:
                            try:
                                await self.viz_sync_service.upsert_from_patient_summary(
                                    full_document
                                )
                            except Exception as e:
                                logger.error(
                                    f"❌ Failed to sync viz document: {e}",
                                    exc_info=True,
                                )

                        await self._save_resume_token(change["_id"])

            except asyncio.CancelledError:
                logger.info("🛑 Viz stream watcher cancelled")
                raise

            except PyMongoError as e:
                error_text = str(e)
                if "ChangeStreamHistoryLost" in error_text or "resume point" in error_text.lower():
                    logger.warning(
                        f"⚠️  Viz stream resume token invalid, restarting from now "
                        f"(run VizSyncService.backfill_all() to repair any gap): {e}"
                    )
                    await self.state_collection.delete_one({"_id": _VIZ_STATE_DOC_ID})
                else:
                    logger.error(
                        f"❌ Viz stream error, reconnecting: {e}", exc_info=True
                    )

                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _MAX_RECONNECT_BACKOFF_SECONDS)

            except Exception as e:
                logger.error(
                    f"❌ Unexpected viz stream error, reconnecting: {e}", exc_info=True
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _MAX_RECONNECT_BACKOFF_SECONDS)

        logger.info("🛑 Viz stream watcher stopped")

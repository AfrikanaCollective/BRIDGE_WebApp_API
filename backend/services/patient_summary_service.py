# backend/services/patient_summary_service.py
"""
Builds/maintains the `patient_summary` collection: one document per patient,
merging the leaf field:value pairs of every processed form under its form
type (ITF / NAR), keyed by patient id.

Source documents live in the parent collection (settings.MONGODB_DB_COLLECTION)
and look like:
    { case_id: "ITF_40000176_page_1.png", form_type: "ITF",
      cleaned_json: { mother_details: {...}, labour_birth: {...}, ... }, ... }

This module is used both by the change-stream watcher (live sync) and the
one-off backfill script (cli/backfill_patient_summary.py), so both stay in
sync via the exact same merge logic.
"""

import logging
from datetime import datetime, UTC
from typing import Any, Dict, Optional

from agents.config import FormType
from clients.mongo_client import MongoClient
from config.settings import settings
from utils.patient_id import extract_patient_id

logger = logging.getLogger(__name__)

_VALID_FORM_TYPES = {form_type.value for form_type in FormType}


def sanitize_key(key: str) -> str:
    """
    Make a field name safe to use as a MongoDB dot-path segment.

    Dot-path updates split on ".", so a literal "." in a field name would be
    misread as nesting; "$"-prefixed keys are also rejected by MongoDB.
    """
    safe = key.replace(".", "_")
    if safe.startswith("$"):
        safe = "_" + safe[1:]
    return safe


def flatten_cleaned_json(cleaned_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten a section-nested cleaned_json into a single level of leaf fields.

    Input:  {"mother_details": {"age": 30, ...}, "labour_birth": {...}}
    Output: {"age": 30, ...}

    Non-dict top-level values are kept as-is (defensive: agents are expected
    to always emit section -> {field: value}, but don't drop data if not).
    """
    flat: Dict[str, Any] = {}
    for section_key, section_value in (cleaned_json or {}).items():
        if isinstance(section_value, dict):
            flat.update(section_value)
        else:
            flat[section_key] = section_value
    return flat


class PatientSummaryService:
    """Maintains the per-patient ITF/NAR summary collection."""

    def __init__(
            self,
            mongo_client: MongoClient,
            db_name: str = settings.MONGODB_DB_NAME,
            collection_name: str = settings.MONGODB_PATIENT_SUMMARY_COLLECTION,
    ):
        self.mongo = mongo_client
        self.db_name = db_name
        self.collection_name = collection_name

        logger.info(
            f"🧬 PatientSummaryService initialized: MongoDB({db_name}.{collection_name})"
        )

    @property
    def collection(self):
        return self.mongo.client[self.db_name][self.collection_name]

    async def upsert_from_document(self, source_doc: Dict[str, Any]) -> Optional[str]:
        """
        Merge a single parent-collection document into patient_summary.

        Returns the patient_id that was upserted, or None if the document
        was skipped (no cleaned_json, unrecognized form type, or no patient
        id could be extracted from the filename).
        """
        if not source_doc:
            return None

        form_type = str(source_doc.get("form_type") or "").upper()
        if form_type not in _VALID_FORM_TYPES:
            logger.debug(f"⏭️  Skipping document with unknown form_type: {form_type!r}")
            return None

        case_id = source_doc.get("case_id") or source_doc.get("image_filename")
        patient_id = extract_patient_id(case_id)
        if not patient_id:
            logger.warning(f"⏭️  Could not extract patient_id from case_id: {case_id!r}")
            return None

        flat_fields = flatten_cleaned_json(source_doc.get("cleaned_json") or {})
        if not flat_fields:
            logger.debug(f"⏭️  No cleaned_json fields to merge for {case_id!r}")
            return None

        now = datetime.now(UTC).isoformat()
        set_fields = {
            f"{form_type}.{sanitize_key(field_name)}": value
            for field_name, value in flat_fields.items()
        }
        set_fields["updated_at"] = now

        await self.collection.update_one(
            {"_id": patient_id},
            {
                "$set": set_fields,
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

        logger.info(
            f"✅ Merged {len(flat_fields)} field(s) into patient_summary: "
            f"patient_id={patient_id}, form_type={form_type}, source={case_id}"
        )
        return patient_id

    async def delete_by_patient_id(self, patient_id: str) -> bool:
        """
        Remove the patient_summary document for patient_id.
        Returns True if a document was deleted, False if none was found.
        """
        if not patient_id:
            return False
        result = await self.collection.delete_one({"_id": patient_id})
        if result.deleted_count:
            logger.info(f"🗑️  Deleted patient_summary: patient_id={patient_id!r}")
            return True
        logger.warning(
            f"⚠️  patient_summary not found for patient_id={patient_id!r} — nothing deleted"
        )
        return False

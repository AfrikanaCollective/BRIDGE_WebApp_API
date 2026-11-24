# backend/tests/extract_key_structure.py

"""
Connects to MongoDB and extracts the unique nested key structure of the
`cleaned_json` field, grouped by (form_type, page_number), across all
documents where status == 'success'.

For each group, keys from every matching document's cleaned_json are unioned
together while preserving the original nested structure. A level of the
structure whose children are all plain (non-dict) values is collapsed into a
sorted list of key names, matching the example format in the request. A
level that contains at least one nested dict is kept as a dict, so nested
substructures aren't flattened away.

Also exports one JSON file covering every document in the collection: each
entry is keyed by the document's `image_filename`, with the value being its
`cleaned_json` flattened down to a single level of leaf key:value pairs
(section/grouping structure discarded).

Also exports per-page timing and token metrics (LLM/agent processing time,
gateway latency, prompt/completion tokens, done_reason, model that answered)
keyed by `image_filename`, for every document regardless of status.

Usage:
    python extract_key_structure.py
    python extract_key_structure.py --db mydb --collection mycoll --output result.json
    python extract_key_structure.py --audit   # audit DB -> *_audit.json outputs
    python extract_key_structure.py --reprocess           # production, post-processing re-run
    python extract_key_structure.py --audit --reprocess   # audit, post-processing re-run

--reprocess re-runs the CURRENT post-model processing (form agents) on each
record's stored raw model output (`raw_json`) instead of using the stored
`cleaned_json`/`coverage`/`completeness`. Use it on both databases so the two
models' results are compared through identical post-processing code. It is
read-only: nothing is written back to MongoDB or MinIO. Outputs get a
`_reprocessed` suffix.
"""

import json
import asyncio
import logging
import argparse
from pathlib import Path
from typing import Any, Dict
from collections import defaultdict
from pymongo import MongoClient
from config.settings import settings

SCRIPT_DIR = Path(__file__).resolve().parent

def merge_keys(existing, new_value):
    """
    Recursively merge the key structure of `new_value` (a value taken from a
    document's cleaned_json) into `existing` (the structure accumulated so
    far for that key/level across previously processed documents).

    Behavior:
      - If new_value is a dict, `existing` becomes/stays a dict mapping each
        key to its recursively merged substructure.
      - If new_value is a leaf (anything that isn't a dict), and `existing`
        isn't already known to be a dict (from another document), `existing`
        becomes a leaf marker (None).
      - If a key is a dict in one document but a plain value in another, the
        dict form wins — nested structure is never discarded once seen,
        since we only care about key shape, not the actual values.
    """
    if isinstance(new_value, dict):
        if not isinstance(existing, dict):
            existing = {}
        for k, v in new_value.items():
            existing[k] = merge_keys(existing.get(k), v)
        return existing
    else:
        if isinstance(existing, dict):
            return existing
        return None  # leaf marker


def structure_to_output(node):
    """
    Convert the internal merged structure (dicts + None leaf markers) into
    the requested output shape:

      - A dict whose values are ALL leaf markers (None) becomes a sorted
        list of its key names — this matches the example in the request,
        e.g. mother_details -> ["mother's_age_in_years", "total_number_of_pregnancies", ...]
      - A dict containing at least one nested dict value is kept as a dict:
        nested keys recurse into their own converted substructure, and any
        leaf keys at that same level are represented with a null value so
        they aren't silently dropped.
    """
    if not isinstance(node, dict):
        return None

    if all(v is None for v in node.values()):
        return sorted(node.keys())

    output = {}
    for k, v in node.items():
        if isinstance(v, dict):
            output[k] = structure_to_output(v)
        else:
            output[k] = None
    return output


def flatten_cleaned_json(value: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively flatten a nested cleaned_json dict down to its leaf
    key:value pairs, discarding section/grouping structure. If the same
    leaf key appears under more than one branch, the last one encountered
    wins.
    """
    flat: Dict[str, Any] = {}

    def _recurse(node: Dict[str, Any]) -> None:
        for key, val in node.items():
            if isinstance(val, dict):
                _recurse(val)
            else:
                flat[key] = val

    _recurse(value)
    return flat


DOCUMENT_PROJECTION = {
    "_id": 0,
    "image_filename": 1,
    "form_type": 1,
    "page_number": 1,
    "status": 1,
    "model": 1,
    "metrics": 1,
    "cleaned_json": 1,
    "coverage": 1,
    "completeness": 1,
    "raw_json": 1,
    "processing_time_llm_seconds": 1,
    "processing_time_agent_seconds": 1,
}


async def _reprocess_documents(docs):
    """Re-run post-model processing on each doc's stored raw_json, in place.

    Feeds the agent exactly what the live pipeline feeds it
    (FormProcessor._process_with_agent on the stored raw model output), and
    derives status with the same rule as StorageService (coverage 0 -> failed).
    """
    from services.form_processor import FormProcessor

    # Agents log a warning per unconvertible field; thousands of docs would
    # bury the progress output.
    for name in ("agents", "services.form_processor"):
        logging.getLogger(name).setLevel(logging.ERROR)

    processor = FormProcessor(storage_service=object())  # storage is never used here
    failed = 0
    for i, doc in enumerate(docs, 1):
        raw = doc.get("raw_json")
        if not raw or not doc.get("image_filename") or not doc.get("form_type"):
            failed += 1
            continue
        _, cleaned_json, _, coverage, completeness = await processor._process_with_agent(
            raw,
            Path(doc["image_filename"]),
            form_type=doc["form_type"],
            page_number=doc.get("page_number"),
        )
        doc["cleaned_json"] = cleaned_json
        doc["coverage"] = coverage
        doc["completeness"] = completeness
        doc["status"] = "failed" if coverage == 0.0 else "success"
        if i % 500 == 0:
            print(f"   ...reprocessed {i}/{len(docs)}")
    print(f"Reprocessed {len(docs) - failed}/{len(docs)} document(s) "
          f"({failed} without raw_json/form_type kept as stored)")


def load_documents(coll, reprocess: bool = False):
    """Load every document once; optionally re-run post-processing on it."""
    docs = list(coll.find({}, DOCUMENT_PROJECTION))
    print(f"Loaded {len(docs)} document(s)")
    if reprocess:
        asyncio.run(_reprocess_documents(docs))
    return docs


def main():

    parser = argparse.ArgumentParser(
        description="Extract unique cleaned_json key structure grouped by form_type/page_number."
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help=(
            "Read from the audit profile's database (QWEN_MODEL_COMPARE results) "
            "and add an '_audit' suffix to every output filename"
        ),
    )
    parser.add_argument(
        "--reprocess",
        action="store_true",
        help=(
            "Re-run the current post-model processing on each record's stored "
            "raw_json (read-only) instead of using the stored cleaned_json"
        ),
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Database name (default: MONGODB_DB_NAME, or the audit DB with --audit)",
    )
    parser.add_argument(
        "--collection",
        default=None,
        help=f"Collection name (default: {settings.MONGODB_DB_COLLECTION})",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to write the combined output JSON (default: mongodb_key_structure[_audit].json)",
    )
    parser.add_argument(
        "--documents-output",
        default=None,
        help=(
            "Path to write the {image_filename: flattened cleaned_json} JSON "
            "covering every document in the collection "
            "(default: llm_dataset[_audit].json)"
        ),
    )
    parser.add_argument(
        "--metrics-output",
        default=None,
        help=(
            "Path to write the per-page {image_filename: timing/token metrics} "
            "JSON covering every document regardless of status "
            "(default: llm_metrics[_audit].json)"
        ),
    )
    args = parser.parse_args()

    # Defaults are resolved after parsing so --audit can switch the DB name
    # (settings.apply_audit_profile mutates the shared settings instance).
    if args.audit:
        settings.apply_audit_profile()
    suffix = ("_audit" if args.audit else "") + ("_reprocessed" if args.reprocess else "")
    args.db = args.db or settings.MONGODB_DB_NAME
    args.collection = args.collection or settings.MONGODB_DB_COLLECTION
    args.output = args.output or f"mongodb_key_structure{suffix}.json"
    args.documents_output = args.documents_output or f"llm_dataset{suffix}.json"
    args.metrics_output = args.metrics_output or f"llm_metrics{suffix}.json"
    print(f"Reading {args.db}.{args.collection}")

    client = MongoClient(settings.get_mongodb_uri())
    coll = client[args.db][args.collection]

    docs = load_documents(coll, reprocess=args.reprocess)
    successful = [d for d in docs if d.get("status") == "success"]

    groups = defaultdict(lambda: None)  # group_name -> merged structure

    doc_count = 0
    skipped = 0

    for doc in successful:
        doc_count += 1

        form_type = doc.get("form_type")
        page_number = doc.get("page_number")
        cleaned_json = doc.get("cleaned_json")

        if form_type is None or page_number is None or not isinstance(cleaned_json, dict):
            skipped += 1
            continue

        group_name = f"{form_type}_{page_number}"
        groups[group_name] = merge_keys(groups[group_name], cleaned_json)

    result = {
        group_name: structure_to_output(structure)
        for group_name, structure in groups.items()
    }

    output_path = SCRIPT_DIR / args.output

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Processed {doc_count} matching document(s) ({skipped} skipped due to missing fields).")
    print(f"Found {len(groups)} group(s): {', '.join(sorted(groups.keys()))}")
    print(f"Result written to: {args.output}")

    # ==================== Per-document flattened export ====================

    documents_by_filename: Dict[str, Any] = {}
    doc_total = 0
    doc_skipped = 0

    for doc in successful:
        doc_total += 1

        image_filename = doc.get("image_filename")
        cleaned_json = doc.get("cleaned_json")

        if not image_filename or not isinstance(cleaned_json, dict):
            doc_skipped += 1
            continue

        documents_by_filename[image_filename] = flatten_cleaned_json(cleaned_json)

    documents_output_path = SCRIPT_DIR / args.documents_output

    with open(documents_output_path, "w", encoding="utf-8") as f:
        json.dump(documents_by_filename, f, indent=2, ensure_ascii=False)

    print(
        f"Processed {doc_total} document(s) for per-file export "
        f"({doc_skipped} skipped due to missing image_filename/cleaned_json)."
    )
    print(f"Wrote {len(documents_by_filename)} document(s) to: {args.documents_output}")

    # ==================== Per-page timing/token metrics export ====================
    # All statuses are included: a page whose extraction failed (coverage 0)
    # still spent LLM time and tokens, which matters when comparing models.

    metrics_by_filename: Dict[str, Any] = {}
    metrics_total = 0
    metrics_skipped = 0

    for doc in docs:
        metrics_total += 1

        image_filename = doc.get("image_filename")
        if not image_filename:
            metrics_skipped += 1
            continue

        llm_metrics = doc.get("metrics") or {}
        prompt_tokens = llm_metrics.get("prompt_eval_count")
        completion_tokens = llm_metrics.get("eval_count")
        total_tokens = (
            prompt_tokens + completion_tokens
            if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int)
            else None
        )

        metrics_by_filename[image_filename] = {
            "form_type": doc.get("form_type"),
            "page_number": doc.get("page_number"),
            "status": doc.get("status"),
            "model": doc.get("model"),
            "backend_used": llm_metrics.get("backend_used"),
            "processing_time_llm_seconds": doc.get("processing_time_llm_seconds"),
            "processing_time_agent_seconds": doc.get("processing_time_agent_seconds"),
            "gateway_latency_ms": llm_metrics.get("latency_ms"),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "done_reason": llm_metrics.get("done_reason"),
            "coverage": doc.get("coverage"),
            "completeness": doc.get("completeness"),
            "reprocessed": bool(args.reprocess),
        }

    metrics_output_path = SCRIPT_DIR / args.metrics_output

    with open(metrics_output_path, "w", encoding="utf-8") as f:
        json.dump(metrics_by_filename, f, indent=2, ensure_ascii=False)

    print(
        f"Processed {metrics_total} document(s) for metrics export "
        f"({metrics_skipped} skipped due to missing image_filename)."
    )
    print(f"Wrote {len(metrics_by_filename)} document(s) to: {args.metrics_output}")

    client.close()


if __name__ == "__main__":
    main()
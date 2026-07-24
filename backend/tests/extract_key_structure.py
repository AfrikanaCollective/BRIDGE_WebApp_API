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

Usage:
    python extract_key_structure.py
    python extract_key_structure.py --db mydb --collection mycoll --output result.json
"""

import json
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


def main():

    parser = argparse.ArgumentParser(
        description="Extract unique cleaned_json key structure grouped by form_type/page_number."
    )
    parser.add_argument(
        "--db",
        default=settings.MONGODB_DB_NAME,
        help=f"Database name (default: {settings.MONGODB_DB_NAME})",
    )
    parser.add_argument(
        "--collection",
        default=settings.MONGODB_DB_COLLECTION,
        help=f"Collection name (default: {settings.MONGODB_DB_COLLECTION})",
    )
    parser.add_argument(
        "--output",
        default="mongodb_key_structure.json",
        help="Path to write the combined output JSON (default: mongodb_key_structure.json)",
    )
    parser.add_argument(
        "--documents-output",
        default="llm_dataset.json",
        help=(
            "Path to write the {image_filename: flattened cleaned_json} JSON "
            "covering every document in the collection "
            "(default: llm_dataset.json)"
        ),
    )
    args = parser.parse_args()

    client = MongoClient(settings.get_mongodb_uri())
    coll = client[args.db][args.collection]

    query = {"status": "success"}
    projection = {"form_type": 1, "page_number": 1, "cleaned_json": 1, "_id": 0}

    groups = defaultdict(lambda: None)  # group_name -> merged structure

    doc_count = 0
    skipped = 0

    for doc in coll.find(query, projection):
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

    documents_projection = {"image_filename": 1, "cleaned_json": 1, "_id": 0}

    documents_by_filename: Dict[str, Any] = {}
    doc_total = 0
    doc_skipped = 0

    query = {"status": "success"}

    for doc in coll.find(query, documents_projection):
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

    client.close()


if __name__ == "__main__":
    main()
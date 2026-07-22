"""
Flatten Images.json into a long-format gold standard dataset.
"""

import json
import re
import pandas as pd
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

def parse_id(id_str: str) -> dict:
    """Parse an _id string like 'NAR_41000118_page_2.png' into components."""
    id_str = re.sub(r"\.png$", "", id_str)  # drop ".png"
    parts = id_str.split("_")               # e.g. ["NAR", "41000118", "page", "2"]

    return {
        "form_type": parts[0],
        "patient_id": parts[1],
        "page": parts[-1],  # last element = page number
    }


def flatten_record(rec: dict) -> pd.DataFrame:
    """Flatten a single record (dict) into long-format rows."""
    id_info = parse_id(rec["_id"])
    fields = {k: v for k, v in rec.items() if k != "_id"}

    rows = []
    for field, value in fields.items():
        # Mirror R's `if (is.null(x)) NA_character_ else as.character(x)`
        if value is None:
            value_str = None
        elif isinstance(value, bool):
            # R's as.character(TRUE/FALSE) -> "TRUE"/"FALSE"
            value_str = "TRUE" if value else "FALSE"
        else:
            value_str = str(value)

        rows.append(
            {
                "hospital": id_info["patient_id"][:2],
                "patient_id": id_info["patient_id"],
                "form_type": id_info["form_type"],
                "page": id_info["page"],
                "field": field,
                "value": value_str,
            }
        )

    return pd.DataFrame(rows)


def main():
    input_path = SCRIPT_DIR / "Images.json"
    output_path = SCRIPT_DIR / "gold_standard_dataset.csv"

    # --- Read the JSON file ---
    with open(input_path, "r") as f:
        json_data = json.load(f)

    # --- Flatten each record into long format ---
    gold_standard_dataset = pd.concat(
        [flatten_record(rec) for rec in json_data],
        ignore_index=True,
    )

    # --- Filter out unwanted rows ---
    # 1. Exclude rows where field == 'hospital'
    gold_standard_dataset = gold_standard_dataset[
        gold_standard_dataset["field"] != "hospital"
    ]

    # 2. Exclude rows where value contains '?' or '@'
    #    NOTE: to match the R behavior exactly (dplyr::filter drops rows
    #    where the condition evaluates to NA), rows with value == None
    #    are ALSO dropped here, since grepl(NA) -> NA -> filtered out in R.
    contains_symbol = gold_standard_dataset["value"].str.contains(
        r"\?|@", regex=True, na=True
    )
    gold_standard_dataset = gold_standard_dataset[~contains_symbol]

    # --- Write to CSV ---
    gold_standard_dataset.to_csv(
        output_path, index=False
    )


if __name__ == "__main__":
    main()
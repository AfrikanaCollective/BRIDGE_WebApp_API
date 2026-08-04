# backend/utils/patient_id.py
"""
Extracts the patient id embedded in form image filenames / case ids.

Filenames follow the pattern <FORM_TYPE>_<PATIENT_ID>_page_<N>.png,
e.g. "ITF_40000176_page_1.png" -> "40000176".
"""

import re
from typing import Optional

from agents.config import FormType

_FORM_TYPE_PREFIXES = "|".join(form_type.value for form_type in FormType)
_PATIENT_ID_PATTERN = re.compile(
    rf"^(?:{_FORM_TYPE_PREFIXES})[_-](\d+)[_-]page",
    re.IGNORECASE,
)


def extract_patient_id(case_id_or_filename: str) -> Optional[str]:
    """
    Extract the patient id from a case_id/image_filename.

    Args:
        case_id_or_filename: e.g. "ITF_40000176_page_1.png" or "NAR_40000176_page_2"

    Returns:
        The patient id string (e.g. "40000176"), or None if it can't be determined.
    """
    if not case_id_or_filename or not isinstance(case_id_or_filename, str):
        return None

    stem = case_id_or_filename.rsplit("/", 1)[-1]
    if "." in stem:
        stem = stem.rsplit(".", 1)[0]

    match = _PATIENT_ID_PATTERN.match(stem)
    return match.group(1) if match else None

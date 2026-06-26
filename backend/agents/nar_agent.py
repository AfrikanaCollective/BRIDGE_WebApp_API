"""NAR Agent - processes NAR (Neonatal Admission Record) forms with multi-page support."""

import re
import logging
from typing import Dict, Any, Optional

from agents.base_agent import BaseAgent
from agents.nar_tools import NARTools
from agents.json_normalizer import JSONNormalizer

logger = logging.getLogger(__name__)

# Section I diagnosis fields (lowercased for case-insensitive matching)
_SECTION_I_DIAGNOSIS_FIELDS = frozenset({
    "prematurity",
    "lbw",
    "birth asphyxia",
    "newborn rds",
    "neonatal sepsis",
    "meconium aspiration",
    "meningitis",
    "congenital anomaly",
    "multiple gestation",
})

# Raw VLM values that represent a positive checkbox selection
_DIAGNOSIS_POSITIVE_VALUES = frozenset({"1", "2"})

# If this many or more diagnosis fields fire simultaneously → hallucination
_MASS_POSITIVE_THRESHOLD = 6


class NARAgent(BaseAgent):
    """Agent for processing NAR (Neonatal Admission Record) documents."""

    def __init__(self, page_number: int = 1):
        if page_number not in [1, 2]:
            raise ValueError(
                f"NAR only supports pages 1 and 2, got {page_number}"
            )
        super().__init__("NAR", page_number)
        self.tools = NARTools(page_number=page_number)


    # ── Abstract hook implementations ───────────────────────────────────────

    def _normalize_json_structure(
        self, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Flatten section headers and clean field names via JSONNormalizer."""
        data = JSONNormalizer.normalize_structure(data)
        data = JSONNormalizer.clean_field_names(data)
        if self.page_number == 2:
            data = self._filter_diagnosis_false_positives(data)
        logger.info("✅ Normalized JSON structure to flat format")
        return data or None  # treat empty dict as failure

    def _filter_diagnosis_false_positives(
        self, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Nullify Section I diagnosis values when mass-positive hallucination is detected.

        Qwen 3.5 9B conflates printed checkbox labels ('1', '2') with checked
        values. When >= _MASS_POSITIVE_THRESHOLD diagnosis fields all return '1'
        or '2' simultaneously, the result is almost certainly hallucinated.
        """
        positive_keys = [
            k for k, v in data.items()
            if k.strip().lower() in _SECTION_I_DIAGNOSIS_FIELDS
            and str(v).strip() in _DIAGNOSIS_POSITIVE_VALUES
        ]
        if len(positive_keys) >= _MASS_POSITIVE_THRESHOLD:
            logger.warning(
                f"⚠️  Mass-positive hallucination detected in Section I: "
                f"{len(positive_keys)}/{len(_SECTION_I_DIAGNOSIS_FIELDS)} "
                f"diagnosis fields returned '1'/'2'. Nullifying all diagnosis values."
            )
            for k in positive_keys:
                data[k] = "N/A"
        return data

    def _fix_prefixed_keys(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove section-letter prefixes (``F1_``, ``G_``, ``H_`` …) from keys.

        Affects < 5% of NAR JSON outputs.  Underscores in the remainder of the
        key are converted back to spaces to restore the original field name.

        Example::

            "F1_Capillary_refill_(Sternal)" → "Capillary refill (Sternal)"
            "J_Vit_K_&_TEO"                → "Vit K & TEO"
        """
        section_prefix_pattern = r"^[A-Z]\d*_"
        fixed: Dict[str, Any] = {}
        keys_fixed = 0

        for key, value in data.items():
            if re.match(section_prefix_pattern, key):
                fixed_key = (
                    re.sub(section_prefix_pattern, "", key)
                    .replace("_", " ")
                )
                fixed[fixed_key] = value
                keys_fixed += 1
                logger.debug(
                    f"✅ Fixed prefixed key: '{key}' → '{fixed_key}'"
                )
            else:
                fixed[key] = value

        if keys_fixed > 0:
            logger.info(
                f"✅ Fixed {keys_fixed} prefixed keys "
                f"(removed section prefixes, converted underscores to spaces)"
            )
        else:
            logger.debug("⏭️  No prefixed keys found - keys are already clean")

        return fixed

    def _collapse_option_keys(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Merge repeated keys that differ only by a Y/N/Pos/Neg option suffix.

        Handles patterns such as::

            "Fever Y": "N/A", "Fever N": "N"  →  "Fever": "N"
            "Blood group A": "A", "Blood group B": "N/A"  →  "Blood group": "A"
            "PMTCT status Pos": "N/A", "PMTCT status Neg": "Neg"
                →  "PMTCT status": "Neg"

        Priority: first non-N/A value wins; ``Y``-suffixed keys take precedence
        over ``N``-suffixed ones when both are non-N/A.
        """
        option_suffixes = [
            " Y", " N",
            " Pos", " Neg", " Unkn",
            " A", " B", " AB", " O",
            " Post", " Emergency", " Elective",
            " <18", " >=18h",
            " Home/roadside", " Other facility",
            " SVD", " CS", " Breech", " Forceps", " Vacuum",
        ]

        key_groups: Dict[str, list] = {}
        collapsed: Dict[str, Any] = {}

        for full_key, value in data.items():
            base_key = full_key
            found = False
            for suffix in option_suffixes:
                if full_key.endswith(suffix):
                    base_key = full_key[: -len(suffix)].strip()
                    found = True
                    break
            if found:
                key_groups.setdefault(base_key, []).append((full_key, value))
            else:
                collapsed[full_key] = value

        for base_key, option_pairs in key_groups.items():
            best_value = None
            prefer_yes = False

            for full_key, value in option_pairs:
                val_str = str(value).strip()
                if val_str.upper() in {"N/A", "NA", ""}:
                    continue
                if best_value is None:
                    best_value = value
                    prefer_yes = full_key.endswith(" Y")
                elif full_key.endswith(" Y") and not prefer_yes:
                    best_value = value
                    prefer_yes = True

            if best_value is not None:
                collapsed[base_key] = best_value
                suffix_info = ", ".join(
                    fk.replace(base_key, "").strip()
                    for fk, _ in option_pairs
                )
                logger.debug(
                    f"✅ Collapsed '{base_key}' [{suffix_info}] "
                    f"→ '{base_key}': {best_value}"
                )
            else:
                logger.debug(
                    f"⏭️  Skipped '{base_key}' - all option values are N/A"
                )

        logger.info(
            f"✅ Collapsed option keys: {len(data)} → {len(collapsed)} keys "
            f"({len(key_groups)} groups collapsed)"
        )
        return collapsed

    def _extract_numeric_values(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """NAR schemas handle units at the schema level — pass-through."""
        return data

    def _get_summary_header(self) -> str:
        return f"=== NAR PAGE {self.page_number} SUMMARY ==="

    # ── Backward-compatible alias ────────────────────────────────────────────

    async def process_nar_file(self, file_path: str) -> Dict[str, Any]:
        """Alias for ``process_file`` — retained for backward compatibility."""
        return await self.process_file(file_path)
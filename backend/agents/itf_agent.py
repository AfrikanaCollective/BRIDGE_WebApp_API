"""ITF Agent - processes ITF (Internal Transfer Form) documents."""

import re
import logging
from typing import Dict, Any, Optional

from config.settings import settings
from agents.base_agent import BaseAgent
from agents.itf_tools import ITFTools
from agents.config import FieldType

logger = logging.getLogger(__name__)


class ITFAgent(BaseAgent):
    """Agent for processing ITF (Internal Transfer Form) documents."""

    def __init__(self, page_number: int = 1):
        super().__init__("ITF", page_number)
        self.tools = ITFTools()

    # ── Abstract hook implementations ───────────────────────────────────────

    def _normalize_json_structure(
        self, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Unwrap the nested ``response`` key that Qwen sometimes emits for ITF.

        Returns the unwrapped dict, the original dict (if no wrapping needed),
        or None if re-extraction of an embedded JSON string fails.
        """
        if "response" not in data:
            return data

        logger.info("⚠️  Unwrapping 'response' key from ITF JSON")
        content_data = data["response"]
        logger.info(
            f"⚠️  response form data (Before) {type(data)}:\n {data}\n"
        )

        if isinstance(content_data, str):
            content_data = content_data.replace("\n", "")
            unwrapped = self._extract_json_from_markdown(content_data)
            logger.info(
                f"⚠️  response form data (After) "
                f"{type(unwrapped)}:\n {unwrapped}\n"
            )
            return unwrapped  # may be None — caller falls through to plain-text

        return data

    def _fix_prefixed_keys(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """ITF keys carry no section prefixes — pass-through."""
        return data

    def _collapse_option_keys(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """ITF has no Y/N suffix patterns — pass-through."""
        return data

    def _extract_numeric_values(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Strip unit suffixes from fields the schema expects as numeric.

        Combines schema INTEGER/FLOAT fields with the allow-list from
        ``settings.NUMERIC_SUFFIX_EXTRACTION_FIELDS``.  Placeholder values
        defined in ``settings.PLACEHOLDER_VALUES`` are preserved as-is.

        Examples:
            ``"120 bpm"``  → ``"120"``
            ``"5.8 °C"``   → ``"5.8"``
            ``"N/A"``      → ``"N/A"``  (placeholder, preserved)
        """
        schema_fields = self._get_all_schema_fields()
        placeholder_values = set(settings.PLACEHOLDER_VALUES)

        extraction_tokens: set = set()

        for schema_key, field_def in schema_fields.items():
            if field_def.get("type") in [FieldType.INTEGER, FieldType.FLOAT]:
                extraction_tokens.add(self._key_token(schema_key))
                logger.debug(
                    f"✅ Added numeric field from schema: {schema_key} "
                    f"({field_def.get('type')})"
                )

        for field_name in settings.NUMERIC_SUFFIX_EXTRACTION_FIELDS:
            extraction_tokens.add(self._key_token(field_name))
            logger.debug(f"✅ Added field from settings: {field_name}")

        if not extraction_tokens:
            logger.debug("⏭️  No numeric extraction fields configured")
            return data

        logger.info(
            f"🔢 Numeric suffix extraction configured for "
            f"{len(extraction_tokens)} fields"
        )

        extracted: Dict[str, Any] = {}
        fields_processed = 0
        fields_skipped = 0

        for key, value in data.items():
            if self._key_token(key) not in extraction_tokens:
                extracted[key] = value
                continue

            val_str = str(value).strip()

            if val_str in placeholder_values:
                extracted[key] = value
                logger.debug(
                    f"⏭️  Preserving placeholder value: {key} = '{val_str}'"
                )
                fields_skipped += 1
                continue

            match = re.search(r"^([-+]?\d*\.?\d+)", val_str)
            if match:
                numeric_value = match.group(1)
                extracted[key] = numeric_value
                fields_processed += 1
                if numeric_value != val_str:
                    logger.debug(
                        f"✅ Extracted numeric: '{key}' = "
                        f"'{val_str}' → '{numeric_value}'"
                    )
                else:
                    logger.debug(
                        f"⏭️  Already numeric: '{key}' = '{val_str}'"
                    )
            else:
                extracted[key] = value
                logger.debug(
                    f"⚠️  No numeric value found: '{key}' = '{val_str}'"
                )

        if fields_processed > 0:
            logger.info(
                f"✅ Extracted numeric values from {fields_processed} fields "
                f"({fields_skipped} skipped as placeholder values)"
            )
        else:
            logger.debug("⏭️  No numeric suffix extraction applied")

        return extracted

    def _split_computed_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Split ``Parity`` ('<live>+<dead>', e.g. '3+0') into ``Parity Live`` / ``Parity Dead``.

        Falls through to the original ``Parity`` key:value pair when the raw
        value contains no ``+``. When the value strips down to a lone ``+``
        (or one side of it is blank), the corresponding derived field is
        omitted so it reads as missing rather than as an empty string.
        """
        parity_key = next(
            (key for key in data if self._key_token(key) == self._key_token("Parity")),
            None,
        )
        if parity_key is None:
            return data

        raw_value = str(data[parity_key]).strip()
        if "+" not in raw_value:
            return data

        live_part, _, dead_part = raw_value.partition("+")
        live_part = live_part.strip()
        dead_part = dead_part.strip()

        split_data = {key: value for key, value in data.items() if key != parity_key}
        if live_part:
            split_data["Parity Live"] = live_part
        if dead_part:
            split_data["Parity Dead"] = dead_part

        logger.info(
            f"✅ Split '{parity_key}'='{raw_value}' → "
            f"Parity Live='{live_part or None}', Parity Dead='{dead_part or None}'"
        )
        return split_data

    def _get_summary_header(self) -> str:
        return "=== CASE SUMMARY ==="

    # ── Backward-compatible alias ────────────────────────────────────────────

    async def process_itf_file(self, file_path: str) -> Dict[str, Any]:
        """Alias for ``process_file`` — retained for backward compatibility."""
        return await self.process_file(file_path)
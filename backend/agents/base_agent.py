"""Base agent - abstract base class for all form processing agents."""

import re
import json
import logging
import unicodedata
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

from agents.config import get_form_schema, ClinicalCategory, FieldType

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all form processing agents.

    Subclasses must implement six abstract hooks:
        _normalize_json_structure  — post-extraction, form-specific JSON fixing
        _fix_prefixed_keys         — remove section-prefix noise from keys
        _collapse_option_keys      — merge Y/N/Pos/Neg suffix variants
        _extract_numeric_values    — strip unit suffixes from numeric fields
        _split_computed_fields     — derive new fields from composite raw values
        _get_summary_header        — first line of the text summary
    """

    def __init__(self, form_type: str, page_number: int):
        self.form_type = form_type
        self.page_number = page_number
        self.schema = get_form_schema(form_type, page_number)
        logger.info(f"🚀 {form_type} Agent initialized (Page {page_number})")
        logger.info(
            f"📋 Loaded {form_type} Page {page_number} Schema "
            f"with {len(self.schema)} field definitions"
        )

    # ── Abstract hooks ──────────────────────────────────────────────────────

    @abstractmethod
    def _normalize_json_structure(
        self, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Form-specific step run immediately after JSON extraction.

        Called only when extraction succeeds.  Must return a dict (possibly
        the same one) or None to signal failure and fall through to plain-text
        parsing.

        NAR: runs JSONNormalizer.normalize_structure + clean_field_names.
        ITF: unwraps nested ``response`` key that Qwen sometimes emits.
        """
        ...

    @abstractmethod
    def _fix_prefixed_keys(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove section-letter prefixes that appear on raw LLM keys.

        NAR: strips ``F1_``, ``G_``, ``H_`` etc. and converts underscores to
        spaces.
        ITF: pass-through (ITF keys carry no such prefixes).
        """
        ...

    @abstractmethod
    def _collapse_option_keys(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Merge repeated keys that differ only by a Y/N/Pos/Neg suffix.

        NAR: collapses ``Fever Y`` / ``Fever N`` → ``Fever``.
        ITF: pass-through (ITF has no such suffix patterns).
        """
        ...

    @abstractmethod
    def _extract_numeric_values(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Strip unit suffixes from fields that the schema expects as numbers.

        ITF: ``"120 bpm"`` → ``"120"`` for INTEGER/FLOAT schema fields and
        fields listed in ``settings.NUMERIC_SUFFIX_EXTRACTION_FIELDS``.
        NAR: pass-through (NAR schemas handle units differently).
        """
        ...

    @abstractmethod
    def _split_computed_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Derive new fields from composite raw values, run right before field-name normalization.

        ITF: splits ``Parity`` ('<live>+<dead>') into ``Parity Live`` /
        ``Parity Dead``.
        NAR: pass-through.
        """
        ...

    @abstractmethod
    def _get_summary_header(self) -> str:
        """Return the form-specific title line for the text summary."""
        ...

    # ── Template method: main processing pipeline ───────────────────────────

    async def process_file(self, file_path: str) -> Dict[str, Any]:
        """Process a form file and return structured extraction results.

        Pipeline (steps that vary per form type are called as abstract hooks):
            1. Read file
            2. Extract JSON from markdown
            3. _normalize_json_structure  ← hook
            4. Plain-text fallback if JSON extraction failed
            5. _flatten_nested_json
            6. _fix_prefixed_keys         ← hook
            7. _collapse_option_keys      ← hook
            8. _extract_numeric_values    ← hook
            9. _split_computed_fields     ← hook
           10. Normalize field names
           11. Convert field types
           12. Categorise into sections
           13. Validate against schema
           14. Extract clinical concepts
           15. Identify risk flags
           16. Generate summary
           17. Compile result dict
        """
        try:
            file_path_obj = Path(file_path)
            logger.info(
                f"📖 Processing: {file_path_obj.name} "
                f"({self.form_type} Page {self.page_number})"
            )

            content = self._read_file(file_path_obj)
            if not content:
                return self._error_result(file_path, "File is empty")

            form_data = self._extract_json_from_markdown(content)

            if form_data:
                form_data = self._normalize_json_structure(form_data)

            if not form_data:
                logger.warning(
                    "⚠️  Could not extract JSON from markdown, "
                    "trying plain text parsing"
                )
                form_data = self._parse_text_form_data(content)

            if not form_data:
                return self._error_result(
                    file_path, "Could not extract form data from file"
                )

            logger.info(f"✅ Extracted {len(form_data)} fields from form")

            form_data = self._flatten_nested_json(form_data)
            logger.info("✅ Flattened nested JSON structure")

            form_data = self._expand_ticked_option_keys(form_data)

            form_data = self._fix_prefixed_keys(form_data)
            logger.info("✅ Fixed prefixed keys")

            form_data = self._collapse_option_keys(form_data)
            logger.info("✅ Collapsed option keys")

            form_data = self._extract_numeric_values(form_data)
            logger.info("✅ Extracted numeric values from suffix fields")

            form_data = self._split_computed_fields(form_data)
            logger.info("✅ Split computed fields")

            normalized = self._normalize_field_names(form_data)
            logger.info("✅ Normalized field names (only schema-defined fields kept)")

            typed = self._convert_field_types(normalized)
            logger.info("✅ Converted field types according to schema")

            sections = self._categorize_into_sections(typed)
            logger.info(f"✅ Categorized into {len(sections)} sections")

            validation = self._validate_against_schema(typed)
            logger.info(
                f"✅ Validated against {self.form_type} "
                f"Page {self.page_number} schema"
            )

            concepts = self._extract_clinical_concepts(typed)
            logger.info(
                f"✅ Extracted {len(concepts)} clinical concept categories"
            )

            risk_flags = self._identify_risk_flags(typed, concepts)
            logger.info(
                f"✅ Identified "
                f"{len(self._flatten_risk_flags(risk_flags))} risk flags"
            )

            summary, coverage, completeness = self._generate_summary(
                typed, sections, risk_flags, validation
            )
            logger.info("✅ Generated summary")

            logger.info(
                f"✅ Successfully processed "
                f"{self.form_type} Page {self.page_number} form"
            )

            return {
                "file": str(file_path_obj),
                "form_type": self.form_type,
                "page": str(self.page_number),
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "raw_data": form_data,
                "normalized_data": normalized,
                "typed_data": typed,
                "sections": sections,
                "validation": validation,
                "clinical_concepts": concepts,
                "risk_assessment": risk_flags,
                "summary": summary,
                "coverage": coverage,
                "completeness": completeness,
                "metadata": {
                    "page_number": self.page_number,
                    "sections_parsed": len(sections),
                    "fields_extracted": len(typed),
                    "clinical_concept_fields": len(concepts),
                    "total_risk_flags": len(
                        self._flatten_risk_flags(risk_flags)
                    ),
                    "schema_fields": len(self._get_canonical_schema_fields()),
                },
            }

        except Exception as e:
            logger.error(f"❌ Error processing file: {e}", exc_info=True)
            return self._error_result(file_path, str(e))

    # ── Shared concrete methods ─────────────────────────────────────────────

    def _read_file(self, file_path: Path) -> Optional[str]:
        try:
            content = file_path.read_text(encoding="utf-8")
            logger.info(f"📖 Read {len(content):,} characters from file")
            return content
        except Exception as e:
            logger.error(f"❌ Error reading file: {e}")
            return None

    def _extract_json_from_markdown(
        self, content: str
    ) -> Optional[Dict[str, Any]]:
        """Extract JSON from a markdown code block or raw JSON content."""
        json_block_pattern = r"```(?:json)?\s*\n(.*?)\n```"
        for match in re.findall(json_block_pattern, content, re.DOTALL):
            result = self._parse_json_string(match.strip())
            if result:
                logger.info("✅ Extracted JSON from markdown code block")
                return result

        lines = content.strip().split("\n")
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                result = self._parse_json_string("\n".join(lines[idx:]))
                if result:
                    logger.info("✅ Extracted JSON from raw content")
                    return result
                break

        return None

    def _parse_json_string(self, json_str: str) -> Optional[Dict[str, Any]]:
        """Parse JSON with three increasingly aggressive fallback strategies."""
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.debug(f"⚠️  Direct JSON parse failed: {e}")

        try:
            cleaned = re.sub(r",(\s*[}\]])", r"\1", json_str)
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        try:
            cleaned = re.sub(r'"\\"([^"]+)\\""', r'"\1"', json_str)
            cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        logger.warning("⚠️  JSON parsing failed, attempting manual extraction")
        return self._extract_kvpairs_from_malformed_json(json_str)

    def _extract_kvpairs_from_malformed_json(
        self, json_str: str
    ) -> Optional[Dict[str, Any]]:
        """Last-resort key-value extraction via regex from heavily malformed JSON."""
        try:
            matches = re.findall(r'"([^"]+)"\s*:\s*"([^"]*)"', json_str)
            if not matches:
                matches = re.findall(
                    r'\\"([^\\"]+)\\"\s*:\s*\\"([^\\"]*)\\"', json_str
                )
            if not matches:
                logger.error("❌ Could not extract any key-value pairs")
                return None
            data = {
                k.replace("\\", ""): v.replace("\\", "") for k, v in matches
            }
            logger.info(
                f"✅ Extracted {len(data)} key-value pairs from malformed JSON"
            )
            return data
        except Exception as e:
            logger.error(f"❌ Error extracting key-value pairs: {e}")
            return None

    def _parse_text_form_data(self, content: str) -> Dict[str, str]:
        """Parse ``key: value`` pairs from plain-text form output."""
        form_data = {}
        for line in content.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("```"):
                continue
            if ":" not in line or line.endswith(":"):
                continue
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip()
            if not key or not value:
                continue
            if key.startswith(("*", "[", "`")) or key.startswith(
                ("A:", "B:", "C:", "D:", "E:", "A.", "B.", "C.", "D.", "E.")
            ):
                continue
            form_data[key] = value

        if form_data:
            logger.info(f"✅ Parsed {len(form_data)} fields from text format")
        else:
            logger.warning("⚠️  No key:value pairs found in text format")
        return form_data

    # Values a model uses to say "this option is the ticked one". ASCII "X"
    # is included because these marks are ONLY honoured on a key that names
    # a schema field plus an option ("Delivery SVD": "X"), where X can only
    # mean "ticked"; a bare "X" field value is never rewritten.
    _TICK_MARKS = {"✓", "✔", "☑", "✅", "√", "✗", "✘", "☒", "X", "x"}
    # Word forms of a tick ("Delivery SVD": "Checked"), compared case-insensitively.
    _TICK_WORDS = {"CHECKED", "TICKED", "MARKED", "SELECTED", "[CHECKED]", "[TICKED]"}
    # Values meaning "this option was not ticked".
    _UNTICKED_VALUES = {"", "N/A", "NA", "n/a", "na", "☐"}
    # Word forms of an empty box, compared case-insensitively.
    _UNTICKED_WORDS = {
        "UNCHECKED", "UNTICKED", "NOT CHECKED", "NOT TICKED", "BLANK", "EMPTY",
        "[UNCHECKED]", "[UNTICKED]", "[BLANK]", "[EMPTY]",
    }
    # Characters that may sit between a section prefix and the field name
    # ("A&B Crackles", "A&B - Crackles", "F1: ... - Skin", "F1_Crackles").
    _FIELD_BOUNDARY = r"(?:^|(?<=[\s:\-–—_/.(&]))"
    # Separator between the field name and the ticked option: a dash/colon
    # (optionally spaced) or plain whitespace ("Crackles - N", "Crackles N").
    _OPTION_SEPARATOR = r"(?:\s*[-–—:]\s*|\s+)"

    @classmethod
    def _is_tick_mark(cls, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        # Drop emoji variation selectors (e.g. "✔️") before comparing.
        stripped = value.replace("\ufe0f", "").strip()
        return stripped in cls._TICK_MARKS or stripped.upper() in cls._TICK_WORDS

    @classmethod
    def _is_unticked(cls, value: Any) -> bool:
        stripped = str(value).strip()
        return stripped in cls._UNTICKED_VALUES or stripped.upper() in cls._UNTICKED_WORDS

    def _ticked_option_patterns(self) -> List[tuple]:
        """(schema_key, compiled pattern) for every schema field name.

        Built once per agent. Field names ending in '?' also match without
        it, since models often drop the question mark ("Birth defects Y").
        """
        cached = getattr(self, "_ticked_option_patterns_cache", None)
        if cached is not None:
            return cached
        patterns = []
        for schema_key, field_def in self._get_all_schema_fields().items():
            names = {schema_key, str(field_def.get("field_name") or schema_key)}
            names |= {n.rstrip("?").strip() for n in names}
            for name in sorted(n for n in names if n):
                pattern = re.compile(
                    self._FIELD_BOUNDARY + r"(?P<field>" + re.escape(name) + r")"
                    + self._OPTION_SEPARATOR + r"(?P<option>\S.*?)\s*$",
                    re.IGNORECASE,
                )
                patterns.append((schema_key, pattern))
        self._ticked_option_patterns_cache = patterns
        return patterns

    def _parse_option_key(self, key: str) -> Optional[tuple]:
        """Split a raw key into (schema_key, option), or None.

        ``"A&B - Crackles N"`` → ``("Crackles", "N")``. Any section prefix
        before the field name is ignored. When several field names occur in
        the key, the one that ENDS nearest the option wins, and on a tie the
        longer name: ``"Neuro Tone Normal"`` → ``Tone`` (not ``Neuro``) and
        ``"Multiple delivery N"`` → ``Multiple delivery`` (not ``Delivery``).
        """
        best = None  # (end, len(name), schema_key, option)
        for schema_key, pattern in self._ticked_option_patterns():
            for match in pattern.finditer(key):
                candidate = (match.end("field"), len(match.group("field")),
                             schema_key, match.group("option"))
                if best is None or candidate[:2] > best[:2]:
                    best = candidate
        return (best[2], best[3]) if best else None

    def _expand_ticked_option_keys(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Rewrite ``"<Field> - <Option>": "✓"`` into ``"<Field>": "<Option>"``.

        Some models report a checkbox by naming the ticked option in the key
        and putting a tick mark in the value (e.g. ``"Crackles - N": "✓"``,
        ``"A&B Crackles N": "✓"``), instead of returning the option as the
        value (``"Crackles": "N"``). This restores the expected shape before
        any key matching or type conversion, so the rest of the pipeline is
        unchanged. Field names come from the loaded schema; keys that do not
        contain a schema field name are left untouched.

        Rules (conservative, never invents a value):
          - Only keys whose value is a tick mark are rewritten.
          - If the field already has a real value under its own key, it wins.
          - If different options of the same field are ticked, the field is
            ambiguous: none are applied and a warning is logged.
          - Once a field is resolved, its unticked sibling keys
            (``"Crackles Y": "N/A"``) are dropped.
        """
        parsed: Dict[str, Optional[tuple]] = {}
        ticked: Dict[str, List[str]] = {}
        for key, value in data.items():
            if not self._is_tick_mark(value):
                continue
            parsed[key] = self._parse_option_key(str(key))
            if parsed[key]:
                schema_key, option = parsed[key]
                options = ticked.setdefault(schema_key, [])
                if option.lower() not in (o.lower() for o in options):
                    options.append(option)

        if not ticked:
            return data

        existing_by_token = {
            self._key_token(str(k)): v for k, v in data.items()
            if not self._is_tick_mark(v)
        }
        resolved: Dict[str, str] = {}
        for schema_key, options in ticked.items():
            existing = existing_by_token.get(self._key_token(schema_key))
            if existing is not None and not self._is_unticked(existing):
                logger.debug(
                    f"⏭️  Ticked options for '{schema_key}' ignored: "
                    f"field already has value {existing!r}"
                )
                continue
            if len(options) > 1:
                logger.warning(
                    f"⚠️  Ambiguous ticks for '{schema_key}': {options} all ticked - field left unset"
                )
                continue
            resolved[schema_key] = options[0]

        expanded: Dict[str, Any] = {}
        for key, value in data.items():
            if self._is_tick_mark(value) and parsed.get(key):
                continue  # consumed into its field below (or ambiguous/overridden)
            if self._is_unticked(value):
                sibling = self._parse_option_key(str(key))
                if sibling and sibling[0] in resolved:
                    continue  # unticked option of a resolved field
            expanded[key] = value
        for field, option in resolved.items():
            expanded[field] = option
            logger.debug(f"✅ Expanded ticked option: '{field} - {option}' → '{field}': {option!r}")

        logger.info(
            f"✅ Expanded {len(resolved)} ticked option key(s) into field values"
            + (f" ({len(ticked) - len(resolved)} skipped)" if len(ticked) != len(resolved) else "")
        )
        return expanded

    def _flatten_nested_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively flatten nested dicts until only leaf key-value pairs remain."""

        def _recurse(obj: Any, path: str = "") -> Dict[str, Any]:
            if not isinstance(obj, dict):
                logger.warning(
                    f"⚠️  Expected dict at '{path}', "
                    f"got {type(obj).__name__}. Skipping."
                )
                return {}
            result = {}
            for key, value in obj.items():
                child_path = f"{path}.{key}" if path else key
                if isinstance(value, dict):
                    result.update(_recurse(value, child_path))
                else:
                    result[key] = value
            return result

        if not any(isinstance(v, dict) for v in data.values()):
            return data

        flattened = _recurse(data)
        logger.info(
            f"✅ Flattened: {len(data)} top-level keys "
            f"→ {len(flattened)} leaf fields"
        )
        return flattened

    def _get_all_schema_fields(self) -> Dict[str, Dict[str, Any]]:
        """Return every field definition dict from the loaded schema."""
        if not isinstance(self.schema, dict):
            return {}
        return {
            name: defn
            for name, defn in self.schema.items()
            if isinstance(defn, dict)
        }

    def _get_canonical_schema_fields(self) -> Dict[str, Dict[str, Any]]:
        """Return schema fields keyed by _key_token(description), deduplicated.

        Schema entries sharing the same description (synonyms) collapse to one
        entry; the first occurrence in schema definition order wins.
        """
        seen: Dict[str, Dict[str, Any]] = {}
        for field_def in self._get_all_schema_fields().values():
            desc = field_def.get("description", "")
            if not desc:
                continue
            canon = self._key_token(desc)
            if canon not in seen:
                seen[canon] = field_def
        return seen

    def _normalize_field_names(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Map raw LLM keys to canonical description-token keys; discard unrecognised keys.

        Schema entries with identical descriptions (synonyms such as
        'APGAR Score 1M' / 'APGAR 1M') collapse to a single output key
        derived from _key_token(description).
        """
        # schema_key_token → canonical description token
        schema_map: Dict[str, str] = {}
        for schema_key, field_def in self._get_all_schema_fields().items():
            desc = field_def.get("description", "")
            canon = self._key_token(desc) if desc else self._key_token(schema_key)
            schema_map[self._key_token(schema_key)] = canon

        logger.debug(
            f"Schema field map created with {len(schema_map)} entries"
        )

        normalized: Dict[str, Any] = {}
        for raw_key, value in data.items():
            try:
                val_str = str(value).strip()
                # "Unknown"/"unkn" are NOT skipped: Unknown is a valid recorded
                # answer, canonicalised to "Unknown" in _convert_single_field.
                # "Unchecked"/"Unticked" = the box was left empty, i.e. N/A; so is a
                # checkbox row with nothing ticked (see _is_nothing_ticked).
                if val_str in {
                    "", "N/A", "n/a", "NA", "na", "N/A + N/A",
                } or val_str.upper() in {"UNCHECKED", "UNTICKED"} \
                        or self._is_empty_with_units(val_str) \
                        or self._is_nothing_ticked(val_str):
                    logger.debug(
                        f"⏭️  Skipping N/A value: {raw_key} = {val_str}"
                    )
                    continue
                canon_key = schema_map.get(self._key_token(raw_key))
                if canon_key:
                    normalized[canon_key] = value
                    logger.debug(f"✅ Matched '{raw_key}' → '{canon_key}'")
                else:
                    logger.debug(
                        f"⏭️  Skipping '{raw_key}' - NOT IN SCHEMA"
                    )
            except Exception as e:
                logger.warning(
                    f"⚠️  Error normalizing field '{raw_key}': {e}"
                )

        logger.info(f"✅ Normalized {len(normalized)} fields")
        return normalized

    def _convert_field_types(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert raw string values to typed values according to the schema."""
        schema_fields = self._get_canonical_schema_fields()
        converted = {}

        for schema_key, raw_value in data.items():
            field_def = schema_fields.get(schema_key)
            if not isinstance(field_def, dict):
                continue
            try:
                converted[schema_key] = self._convert_single_field(
                    schema_key, raw_value, field_def
                )
                logger.debug(
                    f"✅ Converted '{schema_key}': {raw_value!r} → "
                    f"{converted[schema_key]!r} "
                    f"({type(converted[schema_key]).__name__})"
                )
            except Exception as e:
                logger.warning(
                    f"⚠️  Error converting field '{schema_key}': {e}"
                )

        logger.info(f"✅ Converted types for {len(converted)} fields")
        return converted

    def _convert_single_field(
        self, field_name: str, raw_value: Any, field_def: Dict[str, Any]
    ) -> Any:
        """Apply enum mapping then type conversion for a single field."""
        val_str = str(raw_value).strip()

        inline_choice = self._resolve_inline_ticks(val_str)
        if inline_choice is not None:
            logger.debug(f"  ☑️  Resolved inline ticks for '{field_name}': {val_str!r} → {inline_choice!r}")
            raw_value = val_str = inline_choice

        field_type = field_def.get("type")

        # Unknown is a valid recorded answer: any spelling becomes "Unknown"
        # for yes/no, enum and text fields. Numeric fields are excluded on
        # purpose - a string stored there compares greater than every number
        # in MongoDB ($gt in indicators_service), so it would read as e.g. a
        # high respiratory rate. Dates/times keep returning None.
        if (
            val_str.upper() in self._UNKNOWN_TOKENS
            and field_type in self._UNKNOWN_AS_STRING_TYPES
        ):
            return "Unknown"

        enum_mapping = field_def.get("enum_mapping", {})
        if enum_mapping and val_str in enum_mapping:
            raw_value = enum_mapping[val_str]
            val_str = str(raw_value).strip()
            logger.debug(f"  📍 Applied enum mapping: '{val_str}'")

        if field_type == FieldType.BOOLEAN:
            return self._parse_boolean(val_str)

        if field_type in (FieldType.INTEGER, FieldType.FLOAT):
            # Count shorthand: "X6" / "x6" / "6x" / "×6" means 6 (times).
            times = self._TIMES_COUNT.fullmatch(val_str)
            if times:
                val_str = times.group("num") or times.group("num2")
            # Gravida written with its obstetric prefix: "G9" means 9 pregnancies.
            # Only for the Gravida field - elsewhere a "G" is not that prefix.
            elif str(field_def.get("field_name", "")).strip().lower() == "gravida":
                gravida = re.fullmatch(r"\s*[Gg]\s*(\d+)\s*", val_str)
                if gravida:
                    val_str = gravida.group(1)

        if field_type == FieldType.INTEGER:
            try:
                return int(float(val_str))
            except (ValueError, TypeError):
                raise ValueError(f"Cannot convert '{val_str}' to integer")

        if field_type == FieldType.FLOAT:
            try:
                return float(val_str)
            except (ValueError, TypeError):
                raise ValueError(f"Cannot convert '{val_str}' to float")

        if field_type == FieldType.DATE:
            return self._parse_date(
                val_str.replace(" ", ""),
                field_def.get("format", "DD-MM-YYYY"),
            )

        if field_type == FieldType.TIME:
            return self._parse_time(
                val_str.replace(" ", ""),
                field_def.get("format", "HH:MM"),
            )

        if field_type == FieldType.ENUM:
            valid_values = field_def.get("values", [])
            if val_str not in valid_values:
                logger.warning(
                    f"  ⚠️  Value '{val_str}' not in valid enum values "
                    f"{valid_values}"
                )
            return val_str

        return val_str  # STRING, MULTILINE, or unknown type

    # Placeholders for an empty box. N/A and NA must stand alone (so
    # "Nasal flaring" / "Nabugola" are untouched). "[unclear]" is NOT
    # empty - the box had something illegible - so it is left as is.
    _EMPTY_PLACEHOLDER = re.compile(
        r"\[(?:blank|empty|unticked|unchecked)\]|(?<![A-Za-z])N/?A(?![A-Za-z])",
        re.IGNORECASE,
    )
    # Unit suffixes printed next to the box ("N/A /min", "N/A bmp", "N/A °C").
    _EMPTY_UNITS = re.compile(
        r"(?:breaths?/min|beats?/min|[μu]mol/l|mmol/l|mg/dl|g/dl|mmhg|/min|bpm|bmp"
        r"|minutes?|mins?|hours?|hrs?|seconds?|secs?|°c|cm|kg|grams?|weeks?|wks?"
        r"|days?|years?|yrs?|%)",
        re.IGNORECASE,
    )

    @classmethod
    def _is_empty_with_units(cls, val_str: str) -> bool:
        """True for an empty box that carries its printed unit or separators.

        ``"N/A /min"``, ``"N/A bmp"``, ``"N/A / N/A mmHg"``, ``"[blank] cm"``,
        ``"- - hours"``, ``"NA NA minutes"`` → True.
        Also a value whose FIRST line is such an empty box and whose later
        lines are a form heading that leaked in (no digits):
        ``"N/A\\nAPGAR Score"``, ``"N/A bpm\\nAPGAR Score"`` → True.
        A value of only dashes/underscores/dots (``"-"``, ``"- -"``, ``"—"``,
        ``"..."``) → True: a dash is how "nothing written" is recorded.
        ``"+"``/``"++"``/``"+++"`` are real grades (Pallor/Jaundice) and
        ``"/"`` is not a placeholder, so they stay → False.
        Anything with a digit or with words beyond the known unit list
        (``"- Neonatal jaundice"``) → False.
        """
        if not val_str or re.search(r"\d", val_str):
            return False
        if re.fullmatch(r"[\s\-–—_.]+", val_str):
            return True
        first_line, _, later_lines = val_str.partition("\n")
        if later_lines.strip():
            first = first_line.strip()
            return first.upper() in {"N/A", "NA"} or cls._is_empty_with_units(first)
        rest = cls._EMPTY_PLACEHOLDER.sub(" ", val_str)
        had_placeholder = rest != val_str
        rest = cls._EMPTY_UNITS.sub(" ", rest)
        if not re.fullmatch(r"[\s\-/+.,:_]*", rest):
            return False
        # Separators left over ("/", "+") only count as empty if a unit or
        # placeholder was present - "+" alone is a real grade.
        return had_placeholder or rest.strip() != val_str.strip()

    # One number with a single multiplication mark before or after it.
    _TIMES_COUNT = re.compile(r"\s*(?:[xX×]\s*(?P<num>\d+(?:\.\d+)?)|(?P<num2>\d+(?:\.\d+)?)\s*[xX×])\s*")

    _UNKNOWN_TOKENS = {"UNKNOWN", "UNKN", "UNK", "UKN"}
    _UNKNOWN_AS_STRING_TYPES = {
        FieldType.BOOLEAN, FieldType.ENUM, FieldType.STRING, FieldType.MULTILINE, None,
    }

    # Markers a model writes after each printed option of a checkbox row,
    # e.g. "Y [blank] N [ticked] Unkn [blank]".
    _INLINE_TICKED = {"TICKED", "CHECKED", "X", "✓", "✔", "MARKED", "SELECTED"}
    _INLINE_UNTICKED = {"BLANK", "UNTICKED", "UNCHECKED", "EMPTY", "NOT TICKED", "NOT CHECKED"}
    _INLINE_PAIR = re.compile(r"\s*(?P<option>[^\[\],]+?)\s*\[(?P<mark>[^\[\]]+)\]\s*,?")

    # Printed option labels of a yes/no(/unknown) checkbox row.
    _OPTION_LABELS = {"Y", "N", "YES", "NO", "UNKN", "UNK", "UNKNOWN", "POS", "NEG"}

    @classmethod
    def _is_nothing_ticked(cls, val_str: str) -> bool:
        """True for a checkbox row the model read with no option ticked.

        - every option explicitly unticked:
          ``"Y [blank] N [blank]"``, ``"Y [blank] N [blank] Unkn [blank]"``
        - only the printed option labels, no marks at all:
          ``"Y N"``, ``"Y N Unkn"``
        A single label (``"N"``) is a real answer and returns False, as does
        any row with a ticked or unclear box.
        """
        if "[" in val_str:
            pairs = []
            pos = 0
            for match in cls._INLINE_PAIR.finditer(val_str):
                if match.start() != pos:
                    return False
                pairs.append(match.group("mark").strip().upper())
                pos = match.end()
            return (
                len(pairs) >= 2
                and not val_str[pos:].strip()
                and all(mark in cls._INLINE_UNTICKED for mark in pairs)
            )
        tokens = re.split(r"[\s,/]+", val_str.strip().upper())
        return len(tokens) >= 2 and all(t in cls._OPTION_LABELS for t in tokens)

    @classmethod
    def _resolve_inline_ticks(cls, val_str: str) -> Optional[str]:
        """Return the single ticked option of an inline checkbox row, else None.

        ``"Y [blank] N [ticked]"`` → ``"N"``;
        ``"Pos [blank] Neg [ticked] Unkn [blank]"`` → ``"Neg"``.

        Resolves only when the WHOLE value is ``<option> [marker]`` pairs,
        exactly one option is ticked and every other one is explicitly
        unticked. Anything else - nothing ticked, several ticked, any
        ``[unclear]`` (that box might be the ticked one), or a value that
        is not such a row (``[blank]/[blank] mmHg``) - returns None and the
        value is converted exactly as before.
        """
        if "[" not in val_str:
            return None
        pairs = []
        pos = 0
        for match in cls._INLINE_PAIR.finditer(val_str):
            if match.start() != pos:
                return None
            pairs.append((match.group("option").strip(), match.group("mark").strip().upper()))
            pos = match.end()
        if len(pairs) < 2 or val_str[pos:].strip():
            return None
        ticked = [opt for opt, mark in pairs if mark in cls._INLINE_TICKED]
        if len(ticked) != 1:
            return None
        if any(mark not in cls._INLINE_TICKED | cls._INLINE_UNTICKED for _, mark in pairs):
            return None
        return ticked[0]

    def _parse_boolean(self, val_str: str) -> Optional[Union[bool, str]]:
        """Y/N-style value → True/False; "Unknown" (a valid recorded answer)
        → the string "Unknown"; empty → None (not documented)."""
        val_str = val_str.upper().strip()
        # POS/NEG: models sometimes borrow the Pos/Neg/Unkn vocabulary of
        # neighbouring form fields (e.g. PMTCT) for yes/no questions, and
        # ENUM_MAPPINGS expands "Neg" -> "Negative" before this runs.
        if val_str in {"Y", "YES", "TRUE", "1", "T", "POS", "POSITIVE"}:
            return True
        if val_str in {"N", "NO", "FALSE", "0", "F", "NEG", "NEGATIVE"}:
            return False
        if val_str in {"UNKNOWN", "UNKN", "UNK", "UKN"}:
            return "Unknown"
        if val_str == "":
            return None
        raise ValueError(f"Cannot convert '{val_str}' to boolean")

    def _parse_date(
        self, val_str: str, date_format: str
    ) -> Optional[str]:
        val_str = val_str.strip()
        if val_str.upper() in {"UNKNOWN", "UNKN", "UNK", "UKN", ""}:
            return None
        if date_format == "DD-MM-YYYY":
            normalized = self._normalize_dmy_date(val_str)
            if normalized is None:
                raise ValueError(
                    f"Cannot parse date '{val_str}' with format "
                    f"'{date_format}': incomplete (missing digits)"
                )
            val_str = normalized
        try:
            py_fmt = (
                date_format
                .replace("DD", "%d")
                .replace("MM", "%m")
                .replace("YYYY", "%Y")
            )
            return datetime.strptime(val_str, py_fmt).strftime("%Y-%m-%d")
        except ValueError as e:
            raise ValueError(
                f"Cannot parse date '{val_str}' with format "
                f"'{date_format}': {e}"
            )

    _MONTH_NAMES = {
        "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04", "MAY": "05", "JUN": "06",
        "JUL": "07", "AUG": "08", "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12",
    }
    _MONTH_NAME_PATTERN = re.compile(
        r"(?<![A-Z])(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*"
    )

    @classmethod
    def _normalize_dmy_date(cls, val_str: str) -> Optional[str]:
        """Clean an LLM-read DD-MM-YYYY date without inventing digits.

        Forms pre-print ``DD-MM-YYYY`` in the date boxes, so the model often
        returns the handwriting mixed with template letters. Rules:
          - separators ``/ . _`` become ``-``; spaces are removed
          - month names become numbers (``08-MAR-2025`` → ``08-03-2025``)
          - 8 bare digits are read as DDMMYYYY (``13122024``)
          - template letters (D/M/Y) are removed from a part ONLY if the
            digits left fill that part completely (2 for day/month, 4 for
            year): ``24-03M-2024`` → ``24-03-2024``, but ``25-0M-2025`` is
            incomplete (a digit was never written) and returns None
          - a two-digit year is read as 20YY (``07-04-24`` → ``07-04-2024``)

        Returns the cleaned string (which strptime still validates, so
        impossible dates like 30-02-2025 still fail), the input unchanged
        when it isn't a three-part date, or None when digits are missing.
        """
        s = val_str.upper().replace(" ", "")
        s = cls._MONTH_NAME_PATTERN.sub(lambda m: cls._MONTH_NAMES[m.group(1)], s)
        s = re.sub(r"[/._]", "-", s)
        s = re.sub(r"-{2,}", "-", s).strip("-")
        if re.fullmatch(r"\d{8}", s):
            s = f"{s[:2]}-{s[2:4]}-{s[4:]}"

        parts = s.split("-")
        if len(parts) != 3:
            return val_str

        cleaned = []
        for part, placeholder, full_width in zip(parts, "DMY", (2, 2, 4)):
            if not re.fullmatch(r"[0-9DMY]+", part):
                return val_str  # e.g. "[UNCLEAR]": leave for strptime to reject
            if re.search(r"[DMY]", part):
                digits = re.sub(r"[DMY]", "", part)
                if len(digits) != full_width:
                    return None  # template letter stands in for a missing digit
                part = digits
            if placeholder == "Y" and len(part) == 2:
                part = f"20{part}"
            cleaned.append(part)
        return "-".join(cleaned)

    def _parse_time(
        self, val_str: str, time_format: str
    ) -> Optional[str]:
        val_str = val_str.strip()
        if val_str.upper() in {"UNKNOWN", "UNKN", "UNK", "UKN", ""}:
            return None
        try:
            py_fmt = (
                time_format
                .replace("HH", "%H")
                .replace("MM", "%M")
                .replace("SS", "%S")
            )
            parsed = datetime.strptime(val_str, py_fmt)
            if "SS" in time_format.upper():
                return parsed.strftime("%H:%M:%S")
            return parsed.strftime("%H:%M")
        except ValueError as e:
            raise ValueError(
                f"Cannot parse time '{val_str}' with format "
                f"'{time_format}': {e}"
            )

    def _categorize_into_sections(
        self, data: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Group typed fields into sections using schema section definitions."""
        schema_fields = self._get_canonical_schema_fields()
        sections: Dict[str, Dict[str, Any]] = {}

        # Initialise all sections that appear in the schema
        for field_def in schema_fields.values():
            section_enum = field_def.get("section")
            if section_enum:
                section_name = (
                    section_enum.value
                    if hasattr(section_enum, "value")
                    else str(section_enum)
                )
                sections.setdefault(section_name, {})

        # Populate with extracted values
        for schema_key, field_def in schema_fields.items():
            if schema_key not in data:
                continue
            section_enum = field_def.get("section")
            if section_enum:
                section_name = (
                    section_enum.value
                    if hasattr(section_enum, "value")
                    else str(section_enum)
                )
                sections.setdefault(section_name, {})[schema_key] = (
                    data[schema_key]
                )
                logger.debug(
                    f"✅ Placed '{schema_key}' in section "
                    f"'{section_name}' = {data[schema_key]}"
                )

        sections = {k: v for k, v in sections.items() if v}
        logger.info(
            f"✅ Categorized {len(data)} fields into {len(sections)} sections"
        )
        return sections

    def _validate_against_schema(
        self, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check coverage and required-field completeness against the schema."""
        schema_fields = self._get_canonical_schema_fields()

        extracted_fields: List[str] = []
        missing_required: List[str] = []
        documented_required: List[str] = []
        required_fields: List[str] = []
        validation_errors: List[Dict[str, Any]] = []
        documented_count = 0

        for schema_key, field_def in schema_fields.items():
            is_required = field_def.get("required", False)
            if is_required:
                required_fields.append(schema_key)

            if schema_key in data:
                extracted_fields.append(schema_key)
                value = data[schema_key]
                if value is not None:
                    if is_required:
                        documented_required.append(schema_key)
                        documented_count += 1
                    logger.debug(f"✅ Documented: {schema_key} = {value}")
                else:
                    if is_required:
                        missing_required.append(schema_key)
                    logger.debug(
                        f"⏭️  Not documented (null): {schema_key}"
                    )

                validation_rules = field_def.get("validation", {})
                if validation_rules:
                    try:
                        val_num = (
                            float(value)
                            if isinstance(value, (int, float))
                            else float(str(value))
                        )
                        min_val = validation_rules.get("min")
                        max_val = validation_rules.get("max")
                        if min_val is not None and val_num < min_val:
                            validation_errors.append({
                                "field": schema_key,
                                "value": value,
                                "error": f"Below minimum ({min_val})",
                            })
                        if max_val is not None and val_num > max_val:
                            validation_errors.append({
                                "field": schema_key,
                                "value": value,
                                "error": f"Above maximum ({max_val})",
                            })
                    except (ValueError, TypeError):
                        pass
            else:
                if is_required:
                    missing_required.append(schema_key)
                    logger.debug(
                        f"⏭️  Missing required field: {schema_key}"
                    )

        total_required = len(required_fields)
        doc_fraction = (
            documented_count / total_required if total_required > 0 else 0
        )
        doc_pct = doc_fraction * 100
        coverage_pct = (
            len(extracted_fields) / len(schema_fields)
            if schema_fields else 0
        ) * 100

        logger.info(
            f"✅ Required fields documentation: "
            f"{documented_count}/{total_required} ({doc_pct:.1f}%)"
        )

        return {
            "required_fields_valid": len(missing_required) == 0,
            "missing_required_fields": missing_required,
            "documented_required_fields": documented_required,
            "extracted_fields": extracted_fields,
            "extracted_count": len(extracted_fields),
            "total_schema_fields": len(schema_fields),
            "coverage": f"{len(extracted_fields)}/{len(schema_fields)}",
            "coverage_percentage": round(coverage_pct, 2),
            "required_fields_total": total_required,
            "required_fields_documented": documented_count,
            "required_fields_documented_fraction": round(doc_fraction, 4),
            "required_fields_documented_percentage": round(doc_pct, 2),
            "validation_errors": validation_errors,
        }

    def _extract_clinical_concepts(
        self, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Group schema fields marked ``is_clinical_concept`` by category."""
        schema_fields = self._get_canonical_schema_fields()
        clinical_concepts: Dict[str, Any] = {}

        for schema_key, field_def in schema_fields.items():
            if (
                field_def.get("is_clinical_concept", False)
                and schema_key in data
            ):
                category = field_def.get(
                    "clinical_category", ClinicalCategory.OBSERVATION
                )
                category_str = (
                    category.value
                    if isinstance(category, ClinicalCategory)
                    else str(category)
                )
                clinical_concepts.setdefault(category_str, {})[
                    schema_key
                ] = data[schema_key]
                logger.debug(
                    f"✅ Clinical concept: {schema_key} ({category_str})"
                )

        logger.info(
            f"✅ Extracted {len(clinical_concepts)} clinical concept categories"
        )
        return clinical_concepts

    def _identify_risk_flags(
        self,
        data: Dict[str, Any],
        clinical_concepts: Dict[str, Any],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Identify risk flags via boolean flags, enum values, and numeric thresholds."""
        risk_flags: Dict[str, List[Dict[str, Any]]] = {
            "critical": [],
            "high": [],
            "moderate": [],
            "observation": [],
        }
        schema_fields = self._get_canonical_schema_fields()

        for schema_key, data_value in data.items():
            field_def = schema_fields.get(schema_key)
            if not isinstance(field_def, dict):
                continue

            clinical_category = field_def.get(
                "clinical_category", ClinicalCategory.OBSERVATION
            )
            cat = (
                clinical_category.value
                if isinstance(clinical_category, ClinicalCategory)
                else str(clinical_category)
            )

            # Boolean risk flag
            if (
                field_def.get("risk_flag", False)
                and isinstance(data_value, bool)
                and data_value
            ):
                risk_flags[cat].append({
                    "field": schema_key,
                    "value": data_value,
                    "flag": f"{schema_key} present",
                })
                logger.debug(f"🚩 Risk flag: {schema_key} = {data_value}")

            # Single enum risk-flag value
            risk_flag_value = field_def.get("risk_flag_value")
            if risk_flag_value and (
                str(data_value).strip() == str(risk_flag_value).strip()
            ):
                risk_flags[cat].append({
                    "field": schema_key,
                    "value": data_value,
                    "flag": f"{schema_key} = {risk_flag_value}",
                })
                logger.debug(
                    f"🚩 Risk flag: {schema_key} = {risk_flag_value}"
                )

            # Multiple enum risk-flag values
            risk_flag_values = field_def.get("risk_flag_values", [])
            if risk_flag_values and str(data_value).strip() in [
                str(v).strip() for v in risk_flag_values
            ]:
                risk_flags[cat].append({
                    "field": schema_key,
                    "value": data_value,
                    "flag": f"{schema_key} = {data_value}",
                })
                logger.debug(f"🚩 Risk flag: {schema_key} = {data_value}")

            # Numeric threshold checks
            risk_thresholds = field_def.get("risk_thresholds", {})
            if risk_thresholds:
                try:
                    val_num = (
                        float(data_value)
                        if isinstance(data_value, (int, float))
                        else float(str(data_value))
                    )

                    critical = risk_thresholds.get("critical")
                    if critical is not None and val_num <= critical:
                        risk_flags["critical"].append({
                            "field": schema_key,
                            "value": data_value,
                            "flag": (
                                f"{schema_key} critically low "
                                f"(≤{critical})"
                            ),
                        })

                    critical_low = risk_thresholds.get("critical_low")
                    high_low = risk_thresholds.get("high_low")
                    if critical_low and val_num < critical_low:
                        risk_flags["critical"].append({
                            "field": schema_key,
                            "value": data_value,
                            "flag": (
                                f"{schema_key} critically low "
                                f"(<{critical_low})"
                            ),
                        })
                    elif high_low and val_num < high_low:
                        risk_flags["high"].append({
                            "field": schema_key,
                            "value": data_value,
                            "flag": (
                                f"{schema_key} very low (<{high_low})"
                            ),
                        })

                    moderate_low = risk_thresholds.get("moderate_low")
                    if moderate_low and val_num < moderate_low:
                        risk_flags["moderate"].append({
                            "field": schema_key,
                            "value": data_value,
                            "flag": (
                                f"{schema_key} low (<{moderate_low})"
                            ),
                        })
                except (ValueError, TypeError):
                    pass

        return risk_flags

    def _flatten_risk_flags(
        self, risk_flags: Dict[str, List[Dict]]
    ) -> List[Dict]:
        """Flatten nested risk-flag dict to a single list with a severity key."""
        return [
            {**flag, "severity": severity}
            for severity, flags in risk_flags.items()
            for flag in flags
        ]

    def _generate_summary(
        self,
        data: Dict[str, Any],
        sections: Dict[str, Dict],
        risk_flags: Dict[str, List[Dict]],
        val_metrics: Dict[str, Any],
    ) -> tuple:
        """Build a human-readable text summary and return it with coverage metrics."""
        summary = [f"{self._get_summary_header()}\n"]
        schema_fields = self._get_canonical_schema_fields()

        # Build section display order from schema field order
        section_order: Dict[str, str] = {}
        for field_def in schema_fields.values():
            section_enum = field_def.get("section")
            if section_enum:
                section_key = (
                    section_enum.value
                    if hasattr(section_enum, "value")
                    else str(section_enum)
                )
                if section_key not in section_order:
                    section_order[section_key] = (
                        section_key.replace("_", " ").upper()
                    )

        data_coverage = 0.0
        data_req_completeness = 0.0

        for section_key, section_display in section_order.items():
            section_data = sections.get(section_key)
            if not section_data:
                continue

            section_fields = []
            for field_key, field_value in section_data.items():
                if field_value is None:
                    continue
                if isinstance(field_value, str) and field_value == "Unknown":
                    continue

                field_def = schema_fields.get(field_key, {})
                description = field_def.get("description", field_key)
                is_clinical = field_def.get("is_clinical_concept", False)
                clinical_category = field_def.get(
                    "clinical_category", ClinicalCategory.OBSERVATION
                )
                category_str = (
                    clinical_category.value
                    if isinstance(clinical_category, ClinicalCategory)
                    else str(clinical_category)
                )

                if isinstance(field_value, bool):
                    value_str = "Yes" if field_value else "No"
                else:
                    value_str = str(field_value)

                section_fields.append({
                    "description": description,
                    "value": value_str,
                    "is_clinical_concept": is_clinical,
                    "clinical_category": category_str,
                })
                logger.debug(
                    f"✅ Adding to summary [{section_key}]: "
                    f"{description} = {value_str}"
                )

            if section_fields:
                summary.append(f"{section_display}:")
                _indicators = {
                    "critical": "🔴",
                    "high": "🟠",
                    "moderate": "🟡",
                    "administrative": "📋",
                }
                for fi in section_fields:
                    indicator = (
                        _indicators.get(fi["clinical_category"], "•")
                        if fi["is_clinical_concept"]
                        else "•"
                    )
                    summary.append(
                        f"  {indicator} {fi['description']}: {fi['value']}"
                    )
                summary.append("")

        if val_metrics:
            data_req_completeness = val_metrics.get(
                "required_fields_documented_percentage", 0.0
            )
            data_coverage = val_metrics.get("coverage_percentage", 0.0)
            summary += [
                "--- DATA QUALITY ASSESSMENT ---",
                f" Data coverage: {data_coverage:.1f}%",
                f" Data completeness for required fields: "
                f"{data_req_completeness:.1f}%",
                "\n",
            ]

        summary.append("--- RISK ASSESSMENT ---")
        total_flags = len(self._flatten_risk_flags(risk_flags))

        if total_flags > 0:
            summary.append(f"Total Risk Flags: {total_flags}")
            for severity in ["critical", "high", "moderate", "observation"]:
                count = len(risk_flags.get(severity, []))
                if count > 0:
                    summary.append(f"  {severity.upper()}: {count}")

            critical_flags = risk_flags.get("critical", [])
            high_flags = risk_flags.get("high", [])
            if critical_flags or high_flags:
                summary.append("\nFLAGS:")
                for flag in critical_flags[:5]:
                    summary.append(f"  🔴 CRITICAL: {flag['flag']}")
                for flag in high_flags[:5]:
                    summary.append(f"  🟠 HIGH: {flag['flag']}")
        else:
            summary.append("No significant risk flags identified")

        return "\n".join(summary), data_coverage, data_req_completeness

    def _error_result(self, file_path: str, error: str) -> Dict[str, Any]:
        return {
            "file": str(file_path),
            "form_type": self.form_type,
            "page": str(self.page_number),
            "status": "error",
            "error": error,
            "timestamp": datetime.now().isoformat(),
        }

    # ── Export helpers ──────────────────────────────────────────────────────

    def export_json_report(
        self, result: Dict[str, Any], output_path: str
    ) -> None:
        try:
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            with open(output, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            logger.info(f"📄 JSON report exported: {output}")
        except Exception as e:
            logger.error(f"❌ Error exporting JSON report: {e}")

    def export_individual_json(
        self, result: Dict[str, Any], output_path: str
    ) -> None:
        try:
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            with open(output, "w", encoding="utf-8") as f:
                json.dump(result["sections"], f, indent=2, ensure_ascii=False)
            logger.info(f"📄 JSON report exported: {output}")
        except Exception as e:
            logger.error(f"❌ Error exporting JSON report: {e}")

    def export_text_report(
        self, result: Dict[str, Any], output_path: str
    ) -> None:
        try:
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            lines = [
                f"{self.form_type} PAGE {self.page_number} FORM REPORT",
                "=" * 80,
                f"File: {result.get('file', '').split('/')[-1]}",
                f"Status: {result.get('status')}",
                f"Timestamp: {result.get('timestamp')}",
                "=" * 80 + "\n",
            ]
            if result.get("status") == "success":
                lines.append(f"SUMMARY:\n{result.get('summary', '')}\n")
                risk = result.get("risk_assessment", {})
                lines.append("\nRISK ASSESSMENT:")
                for severity in ["critical", "high", "moderate"]:
                    flags = risk.get(severity, [])
                    if flags:
                        lines.append(
                            f"\n  {severity.upper()} ({len(flags)}):"
                        )
                        for flag in flags[:3]:
                            lines.append(
                                f"    • {flag['flag']}: "
                                f"{flag['value']} ({flag['field']})"
                            )
            else:
                lines.append(f"ERROR: {result.get('error')}")
            with open(output, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            logger.info(f"📄 Text report exported: {output}")
        except Exception as e:
            logger.error(f"❌ Error exporting text report: {e}")

    # ── Private key-normalisation helper ───────────────────────────────────

    @staticmethod
    def _key_token(key: str) -> str:
        """Normalise a field name for case-insensitive, punctuation-insensitive comparison."""
        return (
            unicodedata.normalize("NFKC", key)
            .lower()
            .strip()
            .replace("(", "")
            .replace(")", "")
            .replace(" ", "_")
            .replace(".", "")
            .replace(",", "")
            .replace("?", "")
        )
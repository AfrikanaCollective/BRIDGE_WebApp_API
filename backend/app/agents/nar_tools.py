"""NAR-specific tools for form processing."""

import logging
from typing import Dict, Any, List, Tuple, Optional

from app.agents.config import (
    get_form_schema, ClinicalCategory,
    SectionType, NAR_SECTION_VARIATIONS, CLINICAL_CONCEPT_FIELDS,
    FieldType
)
from app.agents.tools import MedicalFormTools

logger = logging.getLogger(__name__)


class NARTools(MedicalFormTools):
    """NAR-specific form processing tools."""

    def __init__(self, page_number: int = 1):
        """
        Initialize NAR tools.

        Args:
            page_number: NAR page number (1 or 2)
        """
        super().__init__("NAR", page_number)
        self.page_number = page_number
        self.schema = get_form_schema('NAR', page_number)
        self.section_variations = NAR_SECTION_VARIATIONS
        self.clinical_concept_fields = CLINICAL_CONCEPT_FIELDS.get("NAR", {}).get(page_number, {})

        logger.info(f"🏥 NAR Tools initialized (Page {page_number})")

    def normalize_section_name(self, raw_section: str) -> Optional[SectionType]:
        """
        Normalize section name to standard SectionType.

        Uses fuzzy matching against known variations.

        Args:
            raw_section: Raw section name from form

        Returns:
            SectionType if matched, None otherwise
        """
        raw_lower = raw_section.lower().strip()

        for canonical, variations in self.section_variations.items():
            for variation in variations:
                if variation.lower() == raw_lower:
                    # Convert string key to SectionType
                    section_type_map = {
                        "INFANT_DETAILS": SectionType.INFANT_DETAILS,
                        "MOTHER_DETAILS": SectionType.MOTHER_DETAILS,
                        "INFANT_HISTORY": SectionType.INFANT_HISTORY,
                        "GENERAL_EXAMINATION": SectionType.GENERAL_EXAMINATION,
                        "FURTHER_EXAMINATION": SectionType.FURTHER_EXAMINATION,
                        "SUMMARY": SectionType.SUMMARY,
                        "INVESTIGATIONS": SectionType.INVESTIGATIONS,
                        "DIAGNOSIS": SectionType.DIAGNOSIS,
                        "INTERVENTIONS": SectionType.INTERVENTIONS,
                        "ACTION_PLAN": SectionType.ACTION_PLAN,
                    }
                    return section_type_map.get(canonical)

        return None

    def parse_nar_form(self, content: str) -> Dict[str, Any]:
        """
        Parse NAR form markdown content.

        Returns:
            {
                "sections": {
                    SectionType: {field: value}
                },
                "unstructured_by_section": {
                    SectionType: [lines]
                },
                "parse_errors": [errors]
            }
        """
        logger.info(f"📖 Parsing NAR Page {self.page_number} form content")

        sections = {}
        unstructured_by_section = {}
        parse_errors = []

        current_section = None
        current_section_type = None
        current_fields = {}
        current_unstructured = []

        lines = content.split('\n')

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()

            if not stripped:
                continue

            # Check if this is a section header
            section_type = self.normalize_section_name(stripped)

            if section_type:
                # Save previous section
                if current_section_type:
                    sections[current_section_type] = current_fields
                    if current_unstructured:
                        unstructured_by_section[current_section_type] = current_unstructured

                # Start new section
                current_section = stripped
                current_section_type = section_type
                current_fields = {}
                current_unstructured = []

                logger.debug(f"📍 Found section: {stripped} → {current_section_type.value}")
                continue

            # Parse field: value pairs
            if ':' in stripped and current_section_type:
                try:
                    parts = stripped.split(':', 1)
                    field = parts[0].strip().strip('"').strip("'").strip('*').strip('_')
                    value = parts[1].strip().strip('"').strip("'") if len(parts) > 1 else None

                    if field and value and value != "N/A":
                        current_fields[field] = value
                        logger.debug(f"  → {field}: {value[:50]}")
                    elif field and not value:
                        current_unstructured.append(stripped)

                except Exception as e:
                    parse_errors.append(f"Line {line_num}: {e}")
                    current_unstructured.append(stripped)
            else:
                # Unstructured content
                if current_section_type and stripped:
                    current_unstructured.append(stripped)

        # Save last section
        if current_section_type:
            sections[current_section_type] = current_fields
            if current_unstructured:
                unstructured_by_section[current_section_type] = current_unstructured

        logger.info(f"✅ Parsed {len(sections)} sections from NAR Page {self.page_number}")

        return {
            "sections": sections,
            "unstructured_by_section": unstructured_by_section,
            "parse_errors": parse_errors
        }

    def extract_clinical_concepts(
            self,
            sections: Dict[SectionType, Dict[str, str]],
            unstructured_by_section: Dict[SectionType, List[str]]
    ) -> Dict[str, Any]:
        """
        Extract clinical concept fields (multiline text fields requiring LLM analysis).

        Returns:
            {
                "clinical_concepts": {
                    SectionType: {
                        field_name: {
                            "raw_value": str,
                            "category": ClinicalCategory,
                            "description": str,
                            "keywords": {severity: [keywords]},
                            "requires_llm": bool
                        }
                    }
                },
                "unstructured_content": {
                    SectionType: [lines]
                }
            }
        """
        logger.info(f"🔍 Extracting clinical concept fields from NAR Page {self.page_number}")

        clinical_concepts = {}

        for section_type, fields in sections.items():
            if section_type not in self.clinical_concept_fields:
                continue

            clinical_concepts[section_type] = {}

            for field_name in fields:
                if field_name in self.clinical_concept_fields.get(section_type, []):

                    if field_name in self.schema:
                        field_config = self.schema[field_name]

                        clinical_concepts[section_type][field_name] = {
                            "raw_value": fields[field_name],
                            "category": field_config.get("clinical_category").value,
                            "description": field_config.get("description"),
                            "keywords": field_config.get("keywords", {}),
                            "requires_llm": field_config.get("type") == FieldType.MULTILINE
                        }

                        logger.debug(f"  → {section_type.value}.{field_name}")

        return {
            "clinical_concepts": clinical_concepts,
            "unstructured_content": unstructured_by_section
        }

    def validate_required_fields(
            self,
            sections: Dict[SectionType, Dict[str, str]]
    ) -> Tuple[bool, List[str]]:
        """
        Validate that all required NAR fields are present.

        Returns:
            (is_valid, missing_fields)
        """
        missing = []

        for field_name, field_config in self.schema.items():
            if field_config.get("required"):
                found = False

                for section_fields in sections.values():
                    if field_name in section_fields:
                        found = True
                        break

                if not found:
                    missing.append(field_name)

        is_valid = len(missing) == 0

        if missing:
            logger.warning(f"⚠️  Missing required fields (NAR Page {self.page_number}): {missing}")
        else:
            logger.info(f"✅ All required fields present (NAR Page {self.page_number})")

        return is_valid, missing

    def validate_field_value(
            self,
            field_name: str,
            value: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate a single field value against schema.

        Returns:
            (is_valid, parsed_value, error_message)
        """
        if field_name not in self.schema:
            return True, value, None  # Unknown field, pass through

        config = self.schema[field_name]
        field_type = config.get("type")

        # Skip N/A values for non-required fields
        if not config.get("required") and (not value or value == "N/A"):
            return True, None, None

        try:
            if field_type == FieldType.DATE:
                is_valid, parsed = self.validate_date(value, config.get("format"))
                return is_valid, parsed, None if is_valid else f"Invalid date: {value}"

            elif field_type == FieldType.TIME:
                is_valid, parsed = self.validate_time(value)
                return is_valid, parsed, None if is_valid else f"Invalid time: {value}"

            elif field_type == FieldType.INTEGER:
                is_valid, parsed = self.validate_integer(
                    value,
                    config.get("validation", {}).get("min"),
                    config.get("validation", {}).get("max")
                )
                return is_valid, parsed, None if is_valid else f"Invalid integer: {value}"

            elif field_type == FieldType.FLOAT:
                is_valid, parsed = self.validate_float(
                    value,
                    config.get("validation", {}).get("min"),
                    config.get("validation", {}).get("max")
                )
                return is_valid, parsed, None if is_valid else f"Invalid float: {value}"

            elif field_type == FieldType.BOOLEAN:
                normalized = self.normalize_boolean(value)
                if normalized is None and config.get("required"):
                    return False, None, f"Invalid boolean: {value}"
                return True, normalized, None

            elif field_type == FieldType.ENUM:
                is_valid, parsed = self.validate_enum(
                    value,
                    config.get("values", [])
                )
                valid_vals = ", ".join(config.get("values", []))
                return is_valid, parsed, None if is_valid else f"Invalid enum (allowed: {valid_vals}): {value}"

            else:  # STRING, MULTILINE
                return True, value, None

        except Exception as e:
            return False, None, str(e)

    def identify_risk_flags(
            self,
            sections: Dict[SectionType, Dict[str, str]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Identify clinical risk flags from extracted fields.

        Returns:
            {
                "critical": [...],
                "high": [...],
                "moderate": [...],
                "observation": [...]
            }
        """
        logger.info(f"🚩 Identifying clinical risk flags (NAR Page {self.page_number})")

        flags = {
            "critical": [],
            "high": [],
            "moderate": [],
            "observation": []
        }

        # Flatten sections
        all_fields = {}
        for section_fields in sections.values():
            all_fields.update(section_fields)

        for field_name, value in all_fields.items():
            if field_name not in self.schema or not value or value == "N/A":
                continue

            config = self.schema[field_name]
            category = config.get("clinical_category")

            if not category or category == ClinicalCategory.ADMINISTRATIVE:
                continue

            flag_obj = {
                "field": field_name,
                "value": value,
                "category": category.value,
                "description": config.get("description")
            }

            # Check boolean flags
            if config.get("type") == FieldType.BOOLEAN:
                normalized = self.normalize_boolean(value)
                if config.get("risk_flag") and normalized is True:
                    flags[category.value].append(flag_obj)
                    logger.debug(f"  → {field_name}: TRUE (risk)")

            # Check enum flags
            elif config.get("type") == FieldType.ENUM:
                if "risk_flag_value" in config and value == config["risk_flag_value"]:
                    flags[category.value].append(flag_obj)
                    logger.debug(f"  → {field_name}: {value} (risk)")
                elif "risk_flag_values" in config and value in config["risk_flag_values"]:
                    flags[category.value].append(flag_obj)
                    logger.debug(f"  → {field_name}: {value} (risk)")

            # Check numeric thresholds
            elif config.get("type") in [FieldType.INTEGER, FieldType.FLOAT]:
                try:
                    num_val = float(value) if config.get("type") == FieldType.FLOAT else int(value)
                    thresholds = config.get("risk_thresholds", {})

                    threshold_flags = []

                    for threshold_name, threshold_val in thresholds.items():
                        if threshold_name.endswith("_low") and num_val < threshold_val:
                            threshold_flags.append(f"{threshold_name}: {num_val} < {threshold_val}")
                        elif threshold_name.endswith("_high") and num_val > threshold_val:
                            threshold_flags.append(f"{threshold_name}: {num_val} > {threshold_val}")
                        elif threshold_name in ["critical", "high", "moderate"]:
                            if isinstance(threshold_val, int) and num_val < threshold_val:
                                threshold_flags.append(f"{threshold_name}: {num_val} < {threshold_val}")

                    if threshold_flags:
                        flag_obj["threshold_violated"] = threshold_flags
                        flags[category.value].append(flag_obj)
                        logger.debug(f"  → {field_name}: {num_val} (threshold violated)")

                except (ValueError, TypeError):
                    pass

        total = sum(len(v) for v in flags.values())
        logger.info(f"✅ Identified {total} risk flags (NAR Page {self.page_number})")

        return flags

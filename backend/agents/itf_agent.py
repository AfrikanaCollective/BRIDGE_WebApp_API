"""ITF Agent - processes ITF forms and extracts structured data."""

import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from agents.itf_tools import ITFTools
from agents.config import get_form_schema, ClinicalCategory, FieldType

logger = logging.getLogger(__name__)


class ITFAgent:
    """Agent for processing ITF (Infant Treatment Form) documents."""

    def __init__(self, page_number: int = 1):
        """Initialize ITF Agent."""
        self.tools = ITFTools()
        self.page_number = page_number
        self.schema = get_form_schema('ITF', page_number)
        logger.info("🚀 ITF Agent initialized")
        logger.info(f"📋 Loaded ITF Schema with {len(self.schema)} field definitions")

    async def process_itf_file(self, file_path: str) -> Dict[str, Any]:
        """
        Process ITF markdown file and extract structured data.

        Args:
            file_path: Path to .md file containing ITF form data

        Returns:
            Dictionary with structured ITF data, risk assessment, and validation
        """
        try:
            file_path_obj = Path(file_path)
            logger.info(f"📖 Processing: {file_path_obj.name}")

            # Read file
            content = self._read_file(file_path_obj)
            if not content:
                return self._error_result(file_path, "File is empty")

            # Extract JSON data from markdown
            form_data = self._extract_json_from_markdown(content)

            if form_data:
                if "response" in form_data:
                    logger.info(f"\n\n⚠️ response form data (Before) {type(form_data)}:\n {form_data}\n")
                    content_data = form_data["response"]
                    logger.info(f"\n\n⚠️ content data (Before) {type(content_data)}:\n {content_data}\n")

                    if isinstance(content_data, str):
                        content_data = content_data.replace("\n", "")
                        json_data = self._extract_json_from_markdown(content_data)
                        form_data = json_data


                    logger.info(f"\n\n⚠️ response form data (After) {type(form_data)}:\n {form_data}\n")

            if not form_data:
                logger.warning(f"⚠️  Could not extract JSON from markdown, trying plain text parsing")
                form_data = self._parse_text_form_data(content)

            logger.info(f"✅ Extracted {len(form_data)} fields from form")

            # Step 0: Flatten json file
            form_data = self._flatten_nested_json(form_data)

            # Step 1: Normalize field names using schema
            normalized_data = self._normalize_field_names(form_data)
            logger.info(f"✅ Normalized field names (only schema-defined fields kept)")

            # Step 2: Convert types according to schema
            typed_data = self._convert_field_types(normalized_data)
            logger.info(f"✅ Converted field types according to schema")

            # Step 3: Categorize into sections using schema
            sections = self._categorize_into_sections(typed_data)
            logger.info(f"✅ Categorized into {len(sections)} sections")

            # Step 4: Validate required fields against schema
            validation = self._validate_against_schema(typed_data)
            logger.info(f"✅ Validated against ITF schema")

            # Step 5: Extract clinical concepts
            clinical_concepts = self._extract_clinical_concepts(typed_data)
            logger.info(f"✅ Extracted {len(clinical_concepts)} clinical concept categories")

            # Step 6: Identify risk flags
            risk_flags = self._identify_risk_flags(typed_data, clinical_concepts)
            logger.info(f"✅ Identified {len(self._flatten_risk_flags(risk_flags))} risk flags")

            # Step 7: Generate summary
            summary, coverage, completeness = self._generate_summary(typed_data, sections, risk_flags, validation)
            logger.info(f"✅ Generated summary")

            # Step 8: Compile result
            result = {
                "file": str(file_path_obj),
                "form_type": "ITF",
                "page": "1",
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "raw_data": form_data,
                "normalized_data": normalized_data,
                "typed_data": typed_data,
                "sections": sections,
                "validation": validation,
                "clinical_concepts": clinical_concepts,
                "risk_assessment": risk_flags,
                "summary": summary,
                "coverage": coverage,
                "completeness": completeness,
                "metadata": {
                    "sections_parsed": len(sections),
                    "fields_extracted": len(typed_data),
                    "clinical_concept_fields": len(clinical_concepts),
                    "total_risk_flags": len(self._flatten_risk_flags(risk_flags)),
                    "schema_fields": len(self._get_all_schema_fields())
                }
            }

            logger.info(f"✅ Successfully processed ITF form")
            return result

        except Exception as e:
            logger.error(f"❌ Error processing file: {e}", exc_info=True)
            return self._error_result(file_path, str(e))

    def _read_file(self, file_path: Path) -> Optional[str]:
        """Read file content."""
        try:
            content = file_path.read_text(encoding='utf-8')
            logger.info(f"📖 Read {len(content):,} characters from file")
            return content
        except Exception as e:
            logger.error(f"❌ Error reading file: {e}")
            return None

    def _extract_json_from_markdown(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON data from markdown file.
        Handles multiple formats and heavily malformed JSON.
        """
        # Pattern 1: JSON in code block
        json_block_pattern = r'```(?:json)?\s*\n(.*?)\n```'
        matches = re.findall(json_block_pattern, content, re.DOTALL)

        if matches:
            for match in matches:
                result = self._parse_json_string(match.strip())
                if result:
                    logger.info(f"✅ Extracted JSON from markdown code block")
                    return result

        # Pattern 2: Raw JSON in content (starts with { or [)
        lines = content.strip().split('\n')

        json_start_idx = None
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('{') or stripped.startswith('['):
                json_start_idx = idx
                break

        if json_start_idx is not None:
            json_str = '\n'.join(lines[json_start_idx:])
            result = self._parse_json_string(json_str)
            if result:
                logger.info(f"✅ Extracted JSON from raw content")
                return result

        return None

    def _parse_json_string(self, json_str: str) -> Optional[Dict[str, Any]]:
        """Parse JSON string with multiple fallback strategies."""
        try:
            data = json.loads(json_str)
            logger.debug(f"✅ Direct JSON parse successful")
            return data

        except json.JSONDecodeError as e:
            logger.debug(f"⚠️  Direct JSON parse failed: {e}")

        # Cleaning attempt 1: Remove trailing commas
        try:
            json_str_clean = re.sub(r',(\s*[}\]])', r'\1', json_str)
            data = json.loads(json_str_clean)
            logger.debug(f"✅ Parsed after removing trailing commas")
            return data
        except json.JSONDecodeError:
            pass

        # Cleaning attempt 2: Fix escaped quotes
        try:
            json_str_clean = re.sub(r'"\\"([^"]+)\\""', r'"\1"', json_str)
            json_str_clean = re.sub(r',(\s*[}\]])', r'\1', json_str_clean)
            data = json.loads(json_str_clean)
            logger.debug(f"✅ Parsed after cleaning escaped quotes")
            return data
        except json.JSONDecodeError:
            pass

        # Last resort: manual key-value extraction
        logger.warning(f"⚠️  JSON parsing failed, attempting manual extraction")
        return self._extract_kvpairs_from_malformed_json(json_str)


    def _flatten_nested_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively flatten nested JSON structure until only leaf key:value pairs remain.

        Handles multiple flattening scenarios:
        1. Top-level sections like "A: Mother's details", "B: Labour and Birth", "C: Infant Details"
        2. Arbitrary nested dictionaries at any level (e.g., 'Labour', 'Delivery', 'Preventive care given')
        3. Mixed structures with both top-level fields and nested dictionaries

        All nested dictionaries are recursively flattened into a single flat dictionary.

        Args:
            data: Input JSON dictionary with possible nested sections and sub-sections

        Returns:
            Completely flattened dictionary with only leaf key:value pairs at the top level
        """

        def _recursive_flatten(obj: Any, parent_path: str = "") -> Dict[
            str, Any]:
            """
            Recursively flatten an object, handling dictionaries and leaf values.

            Args:
                obj: The object to flatten (dict, list, or scalar value)
                parent_path: The path to the current object (for logging)

            Returns:
                Flattened dictionary with leaf key:value pairs
            """
            result = {}

            if not isinstance(obj, dict):
                logger.warning(
                    f"⚠️  Expected dict at '{parent_path}', got {type(obj).__name__}. "
                    f"Skipping this branch.")
                return result

            for key, value in obj.items():
                current_path = f"{parent_path}.{key}" if parent_path else key

                # If value is a dictionary, recursively flatten it
                if isinstance(value, dict):
                    logger.debug(
                        f"📂 Recursing into nested dict: '{current_path}' "
                        f"with {len(value)} fields")
                    nested_flattened = _recursive_flatten(value, current_path)
                    result.update(nested_flattened)
                else:
                    # Leaf value - add to result
                    result[key] = value
                    logger.debug(f"✅ Extracted leaf: {key} = {value}")

            return result

        # Define the section keys to look for (optional optimization)
        section_keys = {
            "A: Mother's details", "A:Mother's details",
            "B: Labour and Birth", 'B:Labour and Birth',
            "C: Infant Details"
        }

        # Check if the data contains any section keys or other nested dicts
        data_keys = set(data.keys())
        has_section_keys = bool(section_keys & data_keys)

        # Check if any top-level values are dictionaries (indicates nesting)
        has_nested_dicts = any(
            isinstance(value, dict) for value in data.values())

        if not has_nested_dicts:
            logger.debug(
                "⏭️  JSON is already completely flat. Returning as-is.")
            return data

        logger.info(f"✅ Found nested structure. "
                    f"Section keys: {len(has_section_keys)}, "
                    f"Nested dicts: {sum(1 for v in data.values() if isinstance(v, dict))}")

        # Recursively flatten all nested structures
        flattened = _recursive_flatten(data)

        logger.info(f"✅ Successfully flattened JSON recursively: "
                    f"{len(data)} top-level keys → {len(flattened)} leaf fields")

        return flattened

    def _extract_kvpairs_from_malformed_json(self, json_str: str) -> Optional[Dict[str, Any]]:
        """Extract key-value pairs from heavily malformed JSON using regex."""
        try:
            data = {}

            pattern1 = r'"([^"]+)"\s*:\s*"([^"]*)"'
            pattern2 = r'\\"([^\\"]+)\\"\s*:\s*\\"([^\\"]*)\\"'

            matches = re.findall(pattern1, json_str)

            if not matches:
                matches = re.findall(pattern2, json_str)

            if not matches:
                logger.error(f"❌ Could not extract any key-value pairs")
                return None

            for key, value in matches:
                key = key.replace('\\', '')
                value = value.replace('\\', '')
                data[key] = value

            logger.info(f"✅ Extracted {len(data)} key-value pairs from malformed JSON")
            return data

        except Exception as e:
            logger.error(f"❌ Error extracting key-value pairs: {e}")
            return None

    def _parse_text_form_data(self, content: str) -> Dict[str, str]:
        """Parse form data from plain text format."""
        form_data = {}
        lines = content.strip().split('\n')

        for line in lines:
            line = line.strip()

            if not line or line.startswith('#') or line.startswith('```'):
                continue

            if line.endswith(':') and ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2 and not parts[1].strip():
                    logger.debug(f"⏭️  Skipping section header: {line}")
                    continue

            if ':' not in line:
                logger.debug(f"⏭️  Skipping non-key:value line: {line}")
                continue

            parts = line.split(':', 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()

                if not key or not value:
                    logger.debug(f"⏭️  Skipping empty key or value: {line}")
                    continue

                if key.startswith(('*', '[', '`')) or key.startswith(('A:', 'B:', 'C:', 'A.', 'B.', 'C.')):
                    logger.debug(f"⏭️  Skipping markdown/header: {line}")
                    continue

                form_data[key] = value
                logger.debug(f"✅ Parsed: {key} = {value}")

        if form_data:
            logger.info(f"✅ Parsed {len(form_data)} fields from text format")
        else:
            logger.warning(f"⚠️  No key:value pairs found in text format")

        return form_data

    def _get_all_schema_fields(self) -> Dict[str, Dict[str, Any]]:
        """Get all fields from ITF schema."""
        all_fields = {}
        if isinstance(self.schema, dict):
            for field_name, field_def in self.schema.items():
                if isinstance(field_def, dict):
                    all_fields[field_name] = field_def
        return all_fields

    def _normalize_field_names(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize field names to match schema keys exactly.
        Only keeps fields that exist in ITF_PAGE_1_SCHEMA.
        """
        normalized = {}
        schema_fields = self._get_all_schema_fields()

        # Create case-insensitive mapping
        schema_field_map = {}
        for schema_key in schema_fields.keys():
            schema_key_normalized = (
                schema_key.lower()
                .strip()
                .replace('(', '')
                .replace(')', '')
                .replace(' ', '_')
                .replace('.', '')
                .replace(',', '')
                .replace('?', '')
            )
            schema_field_map[schema_key_normalized] = schema_key

        logger.debug(f"Schema field map created with {len(schema_field_map)} entries")

        for raw_key, value in data.items():
            try:
                val_str = str(value).strip()

                # Skip empty or placeholder values
                if val_str in ['', 'N/A', 'n/a', 'NA', 'na', 'unknown', 'unkn', 'Unknown', 'UNKNOWN']:
                    logger.debug(f"⏭️  Skipping N/A value: {raw_key} = {val_str}")
                    continue

                raw_key_normalized = (
                    raw_key.lower()
                    .strip()
                    .replace('(', '')
                    .replace(')', '')
                    .replace(' ', '_')
                    .replace('.', '')
                    .replace(',', '')
                    .replace('?', '')
                )

                schema_key = schema_field_map.get(raw_key_normalized)

                if schema_key:
                    # Keep raw value - type conversion happens next
                    normalized[schema_key] = value
                    logger.debug(f"✅ Matched '{raw_key}' → '{schema_key}'")
                else:
                    logger.debug(f"⏭️  Skipping '{raw_key}' - NOT IN SCHEMA")

            except Exception as e:
                logger.warning(f"⚠️  Error normalizing field '{raw_key}': {e}")
                continue

        logger.info(f"✅ Normalized {len(normalized)} fields")
        return normalized

    def _convert_field_types(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert field values to proper types according to schema.
        Applies enum mappings and type conversions.
        """
        converted = {}
        schema_fields = self._get_all_schema_fields()

        for schema_key, raw_value in data.items():
            if schema_key not in schema_fields:
                logger.debug(f"⏭️  Field '{schema_key}' not in schema")
                continue

            field_def = schema_fields[schema_key]
            if not isinstance(field_def, dict):
                continue

            try:
                converted_value = self._convert_single_field(
                    schema_key,
                    raw_value,
                    field_def
                )

                converted[schema_key] = converted_value
                logger.debug(
                    f"✅ Converted '{schema_key}': {raw_value} → {converted_value} ({type(converted_value).__name__})")

            except Exception as e:
                logger.warning(f"⚠️  Error converting field '{schema_key}': {e}")
                continue

        logger.info(f"✅ Converted types for {len(converted)} fields")
        return converted

    def _convert_single_field(self, field_name: str, raw_value: Any, field_def: Dict[str, Any]) -> Any:
        """
        Convert a single field value to proper type.
        Applies enum mapping, then type conversion.
        """
        # Step 1: Apply enum mapping if defined
        val_str = str(raw_value).strip()
        enum_mapping = field_def.get('enum_mapping', {})

        if enum_mapping and val_str in enum_mapping:
            raw_value = enum_mapping[val_str]
            val_str = str(raw_value).strip()
            logger.debug(f"  📍 Applied enum mapping: '{val_str}'")

        # Step 2: Convert to proper type
        field_type = field_def.get('type')

        if field_type == FieldType.BOOLEAN:
            return self._parse_boolean(val_str)

        elif field_type == FieldType.INTEGER:
            try:
                return int(float(val_str))
            except (ValueError, TypeError):
                raise ValueError(f"Cannot convert '{val_str}' to integer")

        elif field_type == FieldType.FLOAT:
            try:
                return float(val_str)
            except (ValueError, TypeError):
                raise ValueError(f"Cannot convert '{val_str}' to float")

        elif field_type == FieldType.DATE:
            return self._parse_date(val_str, field_def.get('format', 'DD-MM-YYYY'))

        elif field_type == FieldType.TIME:
            return self._parse_time(val_str, field_def.get('format', 'HH:MM'))

        elif field_type == FieldType.ENUM:
            # Enum values should be from the values list
            valid_values = field_def.get('values', [])
            if val_str in valid_values:
                return val_str
            else:
                logger.warning(f"  ⚠️  Value '{val_str}' not in valid enum values {valid_values}")
                return val_str

        else:
            # STRING, MULTILINE, or other types
            return val_str

    def _parse_boolean(self, val_str: str) -> Optional[bool]:
        """Parse string to boolean."""
        val_str = val_str.upper().strip()

        if val_str in ['Y', 'YES', 'TRUE', '1', 'T']:
            return True
        elif val_str in ['N', 'NO', 'FALSE', '0', 'F']:
            return False
        elif val_str in ['UNKNOWN', 'UNKN', '']:
            return None
        else:
            raise ValueError(f"Cannot convert '{val_str}' to boolean")

    def _parse_date(self, val_str: str, date_format: str) -> Optional[str]:
        """Parse date string, validate format, return as string in standard format."""
        val_str = val_str.strip()

        if val_str.upper() in ['UNKNOWN', 'UNKN', '']:
            return None

        try:
            # Normalize format string
            py_format = date_format.replace('DD', '%d').replace('MM', '%m').replace('YYYY', '%Y')

            # Parse the date
            parsed_date = datetime.strptime(val_str, py_format)

            # Return in standard format: YYYY-MM-DD
            return parsed_date.strftime('%Y-%m-%d')

        except ValueError as e:
            raise ValueError(f"Cannot parse date '{val_str}' with format '{date_format}': {e}")

    def _parse_time(self, val_str: str, time_format: str) -> Optional[str]:
        """Parse time string, validate format, return as string in standard format."""
        val_str = val_str.strip()

        if val_str.upper() in ['UNKNOWN', 'UNKN', '']:
            return None

        try:
            # Normalize format string
            py_format = time_format.replace('HH', '%H').replace('MM', '%M').replace('SS', '%S')

            # Parse the time
            parsed_time = datetime.strptime(val_str, py_format)

            # Return in standard format: HH:MM:SS or HH:MM
            if 'SS' in time_format.upper():
                return parsed_time.strftime('%H:%M:%S')
            else:
                return parsed_time.strftime('%H:%M')

        except ValueError as e:
            raise ValueError(f"Cannot parse time '{val_str}' with format '{time_format}': {e}")

    def _categorize_into_sections(self, data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Categorize fields into ITF sections using schema.
        Uses typed_data which has been type-converted.
        """
        sections = {
            "mother_details": {},
            "labour_birth": {},
            "infant_details": {}
        }

        schema_fields = self._get_all_schema_fields()

        for schema_field_key, field_def in schema_fields.items():
            if not isinstance(field_def, dict):
                continue

            # Check if this field was extracted
            if schema_field_key not in data:
                continue

            # Get the section from schema definition
            section_enum = field_def.get('section')
            if section_enum:
                if hasattr(section_enum, 'value'):
                    section_name = section_enum.value
                else:
                    section_name = str(section_enum)

                if section_name not in sections:
                    sections[section_name] = {}

                # Use the typed value from data
                sections[section_name][schema_field_key] = data[schema_field_key]
                logger.debug(f"✅ Placed '{schema_field_key}' in section '{section_name}' = {data[schema_field_key]}")

        # Remove empty sections
        sections = {k: v for k, v in sections.items() if v}

        logger.info(f"✅ Categorized {len(data)} fields into {len(sections)} sections")
        return sections

    def _validate_against_schema(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate data against ITF_PAGE_1_SCHEMA.
        data should have canonical schema keys and typed values.
        Includes documentation completeness for required fields.
        """
        schema_fields = self._get_all_schema_fields()

        extracted_fields = []
        missing_required_fields = []
        documented_required_fields = []
        validation_errors = []

        required_fields_list = []
        documented_count = 0

        for schema_field_key, field_def in schema_fields.items():
            if not isinstance(field_def, dict):
                continue

            is_required = field_def.get('required', False)

            if is_required:
                required_fields_list.append(schema_field_key)

            if schema_field_key in data:
                extracted_fields.append(schema_field_key)
                value = data[schema_field_key]

                # Check if field is documented (not None/null)
                if value is not None:
                    if is_required:
                        documented_required_fields.append(schema_field_key)
                        documented_count += 1
                    logger.debug(f"✅ Documented: {schema_field_key} = {value}")
                else:
                    if is_required:
                        missing_required_fields.append(schema_field_key)
                    logger.debug(f"⏭️  Not documented (null): {schema_field_key}")

                # Validate field value
                validation_rules = field_def.get('validation', {})
                if validation_rules:
                    try:
                        val_num = float(value) if isinstance(value, (int, float)) else float(str(value))

                        min_val = validation_rules.get('min')
                        max_val = validation_rules.get('max')

                        if min_val is not None and val_num < min_val:
                            validation_errors.append({
                                "field": schema_field_key,
                                "value": value,
                                "error": f"Below minimum ({min_val})"
                            })

                        if max_val is not None and val_num > max_val:
                            validation_errors.append({
                                "field": schema_field_key,
                                "value": value,
                                "error": f"Above maximum ({max_val})"
                            })

                    except (ValueError, TypeError):
                        pass
            else:
                if is_required:
                    missing_required_fields.append(schema_field_key)
                    logger.debug(f"⏭️  Missing required field: {schema_field_key}")

        # Calculate completeness metrics
        total_required = len(required_fields_list)
        documented_required_fraction = (
            documented_count / total_required if total_required > 0 else 0
        )
        documented_required_percentage = documented_required_fraction * 100
        coverage_percentage = (len(extracted_fields)/len(schema_fields) if len(schema_fields) > 0 else 0) * 100

        logger.info(
            f"✅ Required fields documentation: {documented_count}/{total_required} ({documented_required_percentage:.1f}%)")

        return {
            "required_fields_valid": len(missing_required_fields) == 0,
            "missing_required_fields": missing_required_fields,
            "documented_required_fields": documented_required_fields,
            "extracted_fields": extracted_fields,
            "extracted_count": len(extracted_fields),
            "total_schema_fields": len(schema_fields),
            "coverage": f"{len(extracted_fields)}/{len(schema_fields)}",
            "coverage_percentage":round(coverage_percentage, 2),
            # New: Required fields documentation metrics
            "required_fields_total": total_required,
            "required_fields_documented": documented_count,
            "required_fields_documented_fraction": round(documented_required_fraction, 4),
            "required_fields_documented_percentage": round(documented_required_percentage, 2),
            "validation_errors": validation_errors
        }

    def _extract_clinical_concepts(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract clinically significant fields from schema.
        """
        clinical_concepts = {}
        schema_fields = self._get_all_schema_fields()

        for schema_field_key, field_def in schema_fields.items():
            if not isinstance(field_def, dict):
                continue

            if field_def.get('is_clinical_concept', False) and schema_field_key in data:
                category = field_def.get('clinical_category', ClinicalCategory.OBSERVATION)
                if isinstance(category, ClinicalCategory):
                    category_str = category.value
                else:
                    category_str = str(category)

                if category_str not in clinical_concepts:
                    clinical_concepts[category_str] = {}

                clinical_concepts[category_str][schema_field_key] = data[schema_field_key]
                logger.debug(f"✅ Clinical concept: {schema_field_key} ({category_str})")

        logger.info(f"✅ Extracted {len(clinical_concepts)} clinical concept categories")
        return clinical_concepts

    def _identify_risk_flags(
            self,
            data: Dict[str, Any],
            clinical_concepts: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Identify risk flags based on field values and clinical thresholds from schema.
        """
        risk_flags = {
            "critical": [],
            "high": [],
            "moderate": [],
            "observation": []
        }

        schema_fields = self._get_all_schema_fields()

        for schema_field_key, data_value in data.items():
            if schema_field_key not in schema_fields:
                continue

            field_def = schema_fields[schema_field_key]
            if not isinstance(field_def, dict):
                continue

            clinical_category = field_def.get('clinical_category', ClinicalCategory.OBSERVATION)
            if isinstance(clinical_category, ClinicalCategory):
                category_str = clinical_category.value
            else:
                category_str = str(clinical_category)

            # Check if this is a risk flag field (boolean)
            if field_def.get('risk_flag', False):
                if isinstance(data_value, bool) and data_value:
                    risk_flags[category_str].append({
                        "field": schema_field_key,
                        "value": data_value,
                        "flag": f"{schema_field_key} present"
                    })
                    logger.debug(f"🚩 Risk flag: {schema_field_key} = {data_value}")

            # Check risk flag values (specific enum values that trigger flags)
            risk_flag_value = field_def.get('risk_flag_value')
            if risk_flag_value:
                if str(data_value).strip() == str(risk_flag_value).strip():
                    risk_flags[category_str].append({
                        "field": schema_field_key,
                        "value": data_value,
                        "flag": f"{schema_field_key} = {risk_flag_value}"
                    })
                    logger.debug(f"🚩 Risk flag: {schema_field_key} = {risk_flag_value}")

            # Check risk flag values (multiple enum values)
            risk_flag_values = field_def.get('risk_flag_values', [])
            if risk_flag_values:
                if str(data_value).strip() in [str(v).strip() for v in risk_flag_values]:
                    risk_flags[category_str].append({
                        "field": schema_field_key,
                        "value": data_value,
                        "flag": f"{schema_field_key} = {data_value}"
                    })
                    logger.debug(f"🚩 Risk flag: {schema_field_key} = {data_value}")

            # Check numeric thresholds
            risk_thresholds = field_def.get('risk_thresholds', {})
            if risk_thresholds:
                try:
                    val_num = float(data_value) if isinstance(data_value, (int, float)) else float(str(data_value))

                    critical_threshold = risk_thresholds.get('critical')
                    if critical_threshold is not None and val_num <= critical_threshold:
                        risk_flags["critical"].append({
                            "field": schema_field_key,
                            "value": data_value,
                            "flag": f"{schema_field_key} critically low (≤{critical_threshold})"
                        })
                        logger.debug(f"🚩 CRITICAL: {schema_field_key} = {val_num}")

                    critical_low = risk_thresholds.get('critical_low')
                    high_low = risk_thresholds.get('high_low')

                    if critical_low and val_num < critical_low:
                        risk_flags["critical"].append({
                            "field": schema_field_key,
                            "value": data_value,
                            "flag": f"{schema_field_key} critically low (<{critical_low})"
                        })
                        logger.debug(f"🚩 CRITICAL: {schema_field_key} = {val_num}")
                    elif high_low and val_num < high_low:
                        risk_flags["high"].append({
                            "field": schema_field_key,
                            "value": data_value,
                            "flag": f"{schema_field_key} very low (<{high_low})"
                        })
                        logger.debug(f"🚩 HIGH: {schema_field_key} = {val_num}")

                    moderate_low = risk_thresholds.get('moderate_low')
                    if moderate_low and val_num < moderate_low:
                        risk_flags["moderate"].append({
                            "field": schema_field_key,
                            "value": data_value,
                            "flag": f"{schema_field_key} low (<{moderate_low})"
                        })
                        logger.debug(f"🚩 MODERATE: {schema_field_key} = {val_num}")

                except (ValueError, TypeError):
                    pass

        return risk_flags

    def _flatten_risk_flags(self, risk_flags: Dict[str, List[Dict]]) -> List[Dict]:
        """Flatten risk flags from nested dict to single list."""
        flat = []
        for severity, flags in risk_flags.items():
            for flag in flags:
                flag_copy = flag.copy()
                flag_copy['severity'] = severity
                flat.append(flag_copy)
        return flat

    def _generate_summary(
            self,
            data: Dict[str, Any],
            sections: Dict[str, Dict],
            risk_flags: Dict[str, List[Dict]],
            val_metrics: Dict[str, List[Dict]]
    ) -> str:
        """
        Generate text summary of form using sections data.
        Maps field keys to descriptions from ITF_PAGE_1_SCHEMA.
        Includes all fields from sections (omits None/null values).
        """
        summary = []
        summary.append("=== CASE SUMMARY ===\n")

        schema_fields = self._get_all_schema_fields()

        # Section order for display
        section_order = {
            "mother_details": "MOTHER DETAILS",
            "labour_birth": "LABOUR & BIRTH",
            "infant_details": "INFANT DETAILS"
        }

        # Iterate through sections in order
        for section_key, section_display_name in section_order.items():
            if section_key not in sections:
                continue

            section_data = sections[section_key]
            if not section_data:
                continue

            # Collect fields from this section that have values
            section_fields = []

            for field_key, field_value in section_data.items():
                # Skip None/null values
                if field_value is None:
                    continue

                if isinstance(field_value,str) and field_value == "Unknown":
                    continue

                # Get field definition from schema
                field_def = schema_fields.get(field_key, {})

                # Get description from schema, fallback to field key
                description = field_def.get('description', field_key)

                # Determine if this is a clinical concept
                is_clinical_concept = field_def.get('is_clinical_concept', False)
                clinical_category = field_def.get('clinical_category', ClinicalCategory.OBSERVATION)

                if isinstance(clinical_category, ClinicalCategory):
                    category_str = clinical_category.value
                else:
                    category_str = str(clinical_category)

                # Format value for display
                if isinstance(field_value, bool):
                    value_str = "Yes" if field_value else "No"
                elif isinstance(field_value, (int, float)):
                    value_str = str(field_value)
                elif isinstance(field_value, str):
                    value_str = field_value
                else:
                    value_str = str(field_value)

                section_fields.append({
                    'field_key': field_key,
                    'description': description,
                    'value': value_str,
                    'is_clinical_concept': is_clinical_concept,
                    'clinical_category': category_str
                })

                logger.debug(f"✅ Adding to summary [{section_key}]: {description} = {value_str}")

            # Display section if it has fields
            if section_fields:
                summary.append(f"{section_display_name}:")

                for field_info in section_fields:
                    description = field_info['description']
                    value_str = field_info['value']

                    # Mark clinical concepts with indicators
                    if field_info['is_clinical_concept']:
                        category = field_info['clinical_category']
                        if category == 'critical':
                            indicator = "🔴"
                        elif category == 'high':
                            indicator = "🟠"
                        elif category == 'moderate':
                            indicator = "🟡"
                        elif category == 'administrative':
                            indicator = "📋"
                        else:
                            indicator = "•"
                    else:
                        indicator = "•"

                    summary.append(f"  {indicator} {description}: {value_str}")

                summary.append("")  # Add blank line between sections

        # Add risk assessment summary
        total_flags = len(self._flatten_risk_flags(risk_flags))

        if val_metrics:
            data_req_completeness = val_metrics.get('required_fields_documented_percentage', 0.0)
            data_coverage = val_metrics.get('coverage_percentage', 0.0)

            summary.append("--- DATA QUALITY ASSESSMENT ---")
            summary.append(f" Data coverage: {data_coverage} %")
            summary.append(f" Data completeness for required fields: {data_req_completeness} %")
            summary.append("\n")

        summary.append("--- RISK ASSESSMENT ---")

        if total_flags > 0:
            summary.append(f"Total Risk Flags: {total_flags}")

            flag_counts = {}
            for severity in ["critical", "high", "moderate", "observation"]:
                count = len(risk_flags.get(severity, []))
                if count > 0:
                    flag_counts[severity] = count
                    summary.append(f"  {severity.upper()}: {count}")

            # Display critical and high-risk flags with details
            critical_flags = risk_flags.get("critical", [])
            high_flags = risk_flags.get("high", [])

            if critical_flags or high_flags:
                summary.append(f"\nFLAGS:")
                for flag in critical_flags[:5]:  # Show top 5 critical
                    summary.append(f"  🔴 CRITICAL: {flag['flag']}")
                for flag in high_flags[:5]:  # Show top 5 high
                    summary.append(f"  🟠 HIGH: {flag['flag']}")
        else:
            summary.append(f"No significant risk flags identified")

        case_summary = '\n'.join(summary)

        return case_summary, data_coverage, data_req_completeness

    def _error_result(self, file_path: str, error: str) -> Dict[str, Any]:
        """Generate error result."""
        return {
            "file": str(file_path),
            "form_type": "ITF",
            "page": "1",
            "status": "error",
            "error": error,
            "timestamp": datetime.now().isoformat()
        }

    def export_json_report(self, result: Dict[str, Any], output_path: str):
        """Export result as JSON."""
        try:
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)

            with open(output, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            logger.info(f"📄 JSON report exported: {output}")
        except Exception as e:
            logger.error(f"❌ Error exporting JSON report: {e}")

    def export_individual_json(self, result: Dict[str, Any], output_path: str):
        """Export result as JSON."""
        try:
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)

            with open(output, 'w', encoding='utf-8') as f:
                json.dump(result["sections"], f, indent=2, ensure_ascii=False)

            logger.info(f"📄 JSON report exported: {output}")
        except Exception as e:
            logger.error(f"❌ Error exporting JSON report: {e}")

    def export_text_report(self, result: Dict[str, Any], output_path: str):
        """Export result as text."""
        try:
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)

            lines = []
            lines.append(f"ITF FORM REPORT")
            lines.append(f"{'=' * 80}")
            lines.append(f"File: {result.get('file').split('/')[-1]}")
            lines.append(f"Status: {result.get('status')}")
            lines.append(f"Timestamp: {result.get('timestamp')}")
            lines.append(f"{'=' * 80}\n")

            if result.get('status') == 'success':
                summary = result.get('summary', '')
                lines.append(f"SUMMARY:\n{summary}\n")

                risk = result.get('risk_assessment', {})
                lines.append(f"\nRISK ASSESSMENT:")
                for severity in ["critical", "high", "moderate"]:
                    flags = risk.get(severity, [])
                    if flags:
                        lines.append(f"\n  {severity.upper()} ({len(flags)}):")
                        for flag in flags[:3]:
                            lines.append(f"    • {flag['flag']}: {flag['value']} ({flag['field']})")
            else:
                lines.append(f"ERROR: {result.get('error')}")

            with open(output, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))

            logger.info(f"📄 Text report exported: {output}")
        except Exception as e:
            logger.error(f"❌ Error exporting text report: {e}")

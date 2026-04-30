"""Medical form processing tools."""

import re
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional


logger = logging.getLogger(__name__)


class MedicalFormTools:
    """Base tools for medical form processing."""

    def __init__(self, form_type: str, page: int):
        """Initialize form tools."""
        self.form_type = form_type
        self.page = page
        logger.info(f"🔧 MedicalFormTools initialized: {form_type} Page {page}")

    # ==================== DATE/TIME UTILITIES ====================

    def validate_date(
            self,
            date_str: str,
            format: str = "DD-MM-YYYY"
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate and parse date string.

        Args:
            date_str: Date string to validate
            format: Expected format (DD-MM-YYYY, YYYY-MM-DD, etc.)

        Returns:
            (is_valid, parsed_date_str)
        """
        if not date_str or date_str == "N/A":
            return False, None

        date_str = date_str.strip()

        # Try common formats
        formats = [
            "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y",
            "%Y-%m-%d", "%Y/%m/%d",
            "%d %b %Y", "%d %B %Y",
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(date_str, fmt)
                # Return in standard format
                return True, parsed.strftime("%d-%m-%Y")
            except ValueError:
                continue

        return False, None

    def validate_time(self, time_str: str) -> Tuple[bool, Optional[str]]:
        """
        Validate and parse time string.

        Returns:
            (is_valid, parsed_time_str in HH:MM format)
        """
        if not time_str or time_str == "N/A":
            return False, None

        time_str = time_str.strip()

        formats = ["%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M:%S %p"]

        for fmt in formats:
            try:
                parsed = datetime.strptime(time_str, fmt)
                return True, parsed.strftime("%H:%M")
            except ValueError:
                continue

        return False, None

    # ==================== NUMERIC UTILITIES ====================

    def validate_integer(
            self,
            value: str,
            min_val: Optional[int] = None,
            max_val: Optional[int] = None
    ) -> Tuple[bool, Optional[int]]:
        """
        Validate and parse integer value.

        Args:
            value: String representation of integer
            min_val: Minimum allowed value
            max_val: Maximum allowed value

        Returns:
            (is_valid, parsed_integer)
        """
        if not value or value == "N/A":
            return False, None

        try:
            int_val = int(str(value).strip())

            if min_val is not None and int_val < min_val:
                logger.warning(f"Integer {int_val} below minimum {min_val}")
                return False, None

            if max_val is not None and int_val > max_val:
                logger.warning(f"Integer {int_val} above maximum {max_val}")
                return False, None

            return True, int_val

        except ValueError:
            return False, None

    def validate_float(
            self,
            value: str,
            min_val: Optional[float] = None,
            max_val: Optional[float] = None
    ) -> Tuple[bool, Optional[float]]:
        """
        Validate and parse float value.

        Returns:
            (is_valid, parsed_float)
        """
        if not value or value == "N/A":
            return False, None

        try:
            float_val = float(str(value).strip())

            if min_val is not None and float_val < min_val:
                logger.warning(f"Float {float_val} below minimum {min_val}")
                return False, None

            if max_val is not None and float_val > max_val:
                logger.warning(f"Float {float_val} above maximum {max_val}")
                return False, None

            return True, float_val

        except ValueError:
            return False, None

    # ==================== BOOLEAN UTILITIES ====================

    def normalize_boolean(self, value: str) -> Optional[bool]:
        """
        Normalize string to boolean.

        Returns:
            True, False, or None for ambiguous values
        """
        if not value:
            return None

        value_lower = str(value).strip().lower()

        true_values = ["y", "yes", "true", "1", "positive", "pos", "checked"]
        false_values = ["n", "no", "false", "0", "negative", "neg", "unchecked"]

        if value_lower in true_values:
            return True
        elif value_lower in false_values:
            return False

        return None

    # ==================== ENUM UTILITIES ====================

    def validate_enum(
            self,
            value: str,
            allowed_values: List[str]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate enum value against allowed list.

        Returns:
            (is_valid, value_from_allowed_list or None)
        """
        if not value or value == "N/A":
            return False, None

        value_str = str(value).strip()

        # Exact match
        if value_str in allowed_values:
            return True, value_str

        # Case-insensitive match
        for allowed in allowed_values:
            if allowed.lower() == value_str.lower():
                return True, allowed

        return False, None

    # ==================== STRING UTILITIES ====================

    def normalize_string(self, value: str) -> str:
        """
        Normalize string value.

        - Strip whitespace
        - Remove quotes/underscores
        - Normalize spacing
        """
        if not value:
            return ""

        # Remove leading/trailing quotes
        cleaned = value.strip().strip('"').strip("'").strip('_').strip('*')

        # Normalize internal spacing
        cleaned = re.sub(r'\s+', ' ', cleaned)

        return cleaned

    # ==================== KEYWORD MATCHING ====================

    def detect_keywords(
            self,
            text: str,
            keywords: Dict[str, List[str]]
    ) -> Dict[str, List[str]]:
        """
        Detect keywords in text by severity level.

        Args:
            text: Text to search
            keywords: {severity: [keyword_list]}

        Returns:
            {severity: [found_keywords]}
        """
        if not text:
            return {}

        text_lower = text.lower()
        found = {}

        for severity, kw_list in keywords.items():
            found[severity] = []

            for keyword in kw_list:
                if keyword.lower() in text_lower:
                    found[severity].append(keyword)

        return {k: v for k, v in found.items() if v}

    # ==================== MARKDOWN PARSING ====================

    def extract_markdown_sections(
            self,
            content: str,
            section_marker: str = "#"
    ) -> Dict[str, str]:
        """
        Extract markdown sections by header level.

        Args:
            content: Markdown content
            section_marker: Header marker (# for h1, ## for h2, etc.)

        Returns:
            {section_name: section_content}
        """
        sections = {}
        current_section = None
        current_content = []

        lines = content.split('\n')

        for line in lines:
            if line.strip().startswith(section_marker):
                # Save previous section
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()

                # Start new section
                current_section = line.strip().lstrip(section_marker).strip()
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_section:
            sections[current_section] = '\n'.join(current_content).strip()

        return sections

    def parse_key_value_pairs(
            self,
            text: str,
            delimiter: str = ":"
    ) -> Tuple[Dict[str, str], List[str]]:
        """
        Parse key: value pairs from text.

        Returns:
            (parsed_pairs, unparsed_lines)
        """
        pairs = {}
        unparsed = []

        for line in text.split('\n'):
            line = line.strip()

            if not line:
                continue

            if delimiter in line:
                key, value = line.split(delimiter, 1)
                key = key.strip().strip('"').strip("'").strip('*').strip('_')
                value = value.strip().strip('"').strip("'")

                if key and value and value != "N/A":
                    pairs[key] = value
            else:
                unparsed.append(line)

        return pairs, unparsed

    # ==================== CODE BLOCK STRIPPING ====================

    def strip_code_blocks(self, text: str) -> str:
        """
        Remove markdown code blocks from text.

        Handles:
        - Triple backticks (with or without language)
        - Indented code blocks
        """
        if not text:
            return ""

        # Remove triple backtick blocks
        text = re.sub(r'```[\w]*\n(.*?)\n```', r'\1', text, flags=re.DOTALL)

        # Remove inline code
        text = re.sub(r'`([^`]+)`', r'\1', text)

        return text

    # ==================== FORM PARSING ====================

    def parse_markdown_to_dict(
            self,
            content: str
    ) -> Tuple[Dict[str, Dict[str, str]], List[str]]:
        """
        Parse markdown form content to structured data.

        Args:
            content: Markdown content from form

        Returns:
            (structured_sections, unstructured_lines)
        """
        logger.info("📖 Parsing markdown to dictionary")

        # Strip code blocks first
        content = self.strip_code_blocks(content)

        sections = {}
        unstructured_lines = []

        # Parse key: value pairs
        pairs, unparsed = self.parse_key_value_pairs(content)

        logger.info(f"✅ Parsed {len(pairs)} key-value pairs, {len(unparsed)} unparsed lines")

        return pairs, unparsed

    def structure_form_data(
            self,
            parsed_data: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Structure parsed form data with validation.

        Returns:
            {
                'structured_data': {section: {field: value}},
                'validation_errors': [...],
                'validation_warnings': [...]
            }
        """
        return {
            "structured_data": {},
            "validation_errors": [],
            "validation_warnings": [],
            "section_presence": {}
        }

    # ==================== CLINICAL FLAG EXTRACTION ====================

    def extract_clinical_flags(
            self,
            structured_data: Dict[str, Any],
            unstructured_content: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract clinical significance flags from form data.

        Returns:
            {
                'critical': [...],
                'high': [...],
                'moderate': [...],
                'observation': [...]
            }
        """
        return {
            "critical": [],
            "high": [],
            "moderate": [],
            "observation": []
        }

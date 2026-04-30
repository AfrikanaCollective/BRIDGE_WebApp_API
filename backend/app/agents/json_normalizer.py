"""JSON normalization and flattening utilities."""

import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class JSONNormalizer:
    """Handles JSON structure normalization and flattening."""

    @staticmethod
    def is_flat(data: Dict[str, Any]) -> bool:
        """
        Check if JSON structure is flat (no nested dicts).

        Args:
            data: JSON object to check

        Returns:
            True if structure is flat (all values are scalars)
        """
        if not isinstance(data, dict):
            return False

        for value in data.values():
            if isinstance(value, dict):
                return False
            if isinstance(value, list) and any(isinstance(item, dict) for item in value):
                return False

        return True

    @staticmethod
    def flatten(data: Dict[str, Any], parent_key: str = '') -> Dict[str, Any]:
        """
        Flatten nested JSON structure.

        Args:
            data: Nested JSON object
            parent_key: Parent key for recursion

        Returns:
            Flat dictionary
        """
        items = []

        for key, value in data.items():
            new_key = f"{parent_key}_{key}" if parent_key else key

            if isinstance(value, dict):
                # Recursively flatten nested dicts
                items.extend(JSONNormalizer.flatten(value, new_key).items())
            elif isinstance(value, list):
                # Skip lists, keep as-is
                items.append((new_key, value))
            else:
                # Keep scalar values
                items.append((new_key, value))

        return dict(items)

    @staticmethod
    def remove_section_headers(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove section headers from nested structure.

        Converts:
        {
            "A: Infant Details": {"Name": "...", "DOB": "..."},
            "B: Mother's Details": {"Age": "..."}
        }

        To:
        {
            "Name": "...",
            "DOB": "...",
            "Age": "..."
        }

        Args:
            data: Potentially nested JSON

        Returns:
            Flattened dictionary
        """
        if JSONNormalizer.is_flat(data):
            return data

        flattened = {}

        for key, value in data.items():
            if isinstance(value, dict):
                # This is a section - merge its contents
                logger.debug(f"Found section: {key}")
                flattened.update(value)
            else:
                # Keep scalar values
                flattened[key] = value

        return flattened

    @staticmethod
    def normalize_structure(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize JSON structure to flat format.

        Handles both flat and nested inputs.

        Args:
            data: JSON object

        Returns:
            Normalized flat dictionary
        """
        if not isinstance(data, dict):
            logger.warning(f"Input is not a dict: {type(data)}")
            return {}

        # First, try to flatten section headers
        flat = JSONNormalizer.remove_section_headers(data)

        # Then, recursively flatten any remaining nested structures
        while not JSONNormalizer.is_flat(flat):
            logger.debug("Flattening nested structures...")
            flat = JSONNormalizer.flatten(flat)

        logger.info(f"✅ Normalized to flat structure with {len(flat)} fields")
        return flat

    @staticmethod
    def clean_field_names(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean field names (strip extra whitespace, etc.).

        Args:
            data: Dictionary with field names to clean

        Returns:
            Dictionary with cleaned field names
        """
        cleaned = {}

        for key, value in data.items():
            # Strip whitespace
            clean_key = key.strip()
            # Remove leading/trailing special characters
            clean_key = clean_key.strip('"\'*_-')
            # Collapse multiple spaces
            clean_key = ' '.join(clean_key.split())

            cleaned[clean_key] = value

        return cleaned

    @staticmethod
    def remove_null_values(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove N/A and null values from data.

        Args:
            data: Dictionary to clean

        Returns:
            Dictionary without N/A/null values
        """
        cleaned = {}

        for key, value in data.items():
            # Keep all values, including N/A (agent will handle)
            if value is not None and value != "":
                cleaned[key] = value

        return cleaned

    @staticmethod
    def validate_and_normalize(json_str: str) -> Optional[Dict[str, Any]]:
        """
        Parse, validate, and normalize JSON string.

        Args:
            json_str: JSON string to process

        Returns:
            Normalized flat dictionary or None if parsing fails
        """
        try:
            # Parse JSON
            data = json.loads(json_str)

            if not isinstance(data, dict):
                logger.error(f"JSON root is not a dict: {type(data)}")
                return None

            logger.debug(f"✅ Parsed JSON with {len(data)} top-level keys")

            # Normalize structure
            normalized = JSONNormalizer.normalize_structure(data)

            # Clean field names
            normalized = JSONNormalizer.clean_field_names(normalized)

            logger.info(f"✅ Validated and normalized JSON")
            return normalized

        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parse error: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Normalization error: {e}")
            return None

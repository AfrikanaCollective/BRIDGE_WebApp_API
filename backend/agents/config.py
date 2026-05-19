# backend/agents/config.py
"""
Agent configuration and constants - Enums, mappings, and utility functions.
Page-specific schemas are loaded from separate files.
"""

from enum import Enum
from typing import Dict, Any, List


# ==================== ENUMS ====================

class FormType(Enum):
    """Supported form types."""
    ITF = "ITF"  # Internal Transfer Form (1 page)
    NAR = "NAR"  # Neonatal Admission Record (2 pages)


class FieldType(Enum):
    """Field data types."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    TIME = "time"
    ENUM = "enum"
    MULTILINE = "multiline"


class SectionType(Enum):
    """Section types for ITF & NAR """
    MOTHER_DETAILS = "mother_details"
    LABOUR_BIRTH = "labour_birth"
    INFANT_DETAILS = "infant_details"
    INFANT_HISTORY = "infant_history"
    GENERAL_EXAMINATION = "general_examination"
    FURTHER_EXAMINATION = "further_examination"
    SUMMARY = "summary"
    INVESTIGATIONS = "investigations"
    DIAGNOSIS = "diagnosis"
    INTERVENTIONS = "interventions"
    ACTION_PLAN = "action_plan"


class ClinicalCategory(Enum):
    """Clinical significance categories."""
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    OBSERVATION = "observation"
    ADMINISTRATIVE = "administrative"


# ==================== SECTION VARIATIONS ====================

ITF_SECTION_VARIATIONS = {
    "MOTHER_DETAILS": [
        "A: Mother's details",
        "A: Mothers details",
        "Mother's details",
        "Mother details",
        "A: Maternal Details",
    ],
    "LABOUR_BIRTH": [
        "B: Labour and Birth",
        "B: Labour and birth",
        "Labour and Birth",
        "Labour and birth",
        "B: Labour Details",
    ],
    "INFANT_DETAILS": [
        "C: Infant Details",
        "C: Infant details",
        "Infant Details",
        "Infant details",
        "C: Baby Details",
        "C: Neonatal Details",
    ],
}

NAR_SECTION_VARIATIONS = {
    # To be defined based on NAR form structure
    "INFANT_DETAILS": [
        "A: Infant Details",
        "A: Infant details",
        "Infant Details",
        "Infant details",
    ],
    "MOTHER_DETAILS": [
        "B: Mother's details",
        "B: Mothers details",
        "Mother's details",
        "Mothers details",
        "C: Mother's problems during pregnancy/labour & relevant maternal treatment",
        "Mother's problems during pregnancy/labour & relevant maternal treatment",
        "Mothers problems during pregnancy labour & relevant maternal treatment",
    ],
    "INFANT_HISTORY": [
        "D: Infant's presenting problem & any treatment given",
        "Infant's presenting problem & any treatment given",
        "E: History and examination",
        "History and examination",
    ],
    "GENERAL_EXAMINATION": [
        "F1: General examination",
        "General examination"
    ],
    "FURTHER_EXAMINATION": [
        "F2: Further examination",
        "Further examination"
    ],
    "SUMMARY": [
        "G: Summary of presentation and problems (List most important problems first)",
        "Summary of presentation and problems (List most important problems first)"
    ],
    "INVESTIGATIONS": [
        "H: Investigations ordered",
    ],
    "DIAGNOSIS": [
        "I: Admission Diagnoses or Impression",
        "Admission Diagnoses or Impression",
    ],
    "INTERVENTIONS": [
        "J: Interventions prescribed, and preventive care given"
        "Interventions prescribed, and preventive care given"
    ],
    "ACTION_PLAN": [
        "K: Action plan",
        "Action plan"
    ]

}

# ==================== CLINICAL CONCEPT FIELDS ====================
# Fields that require LLM analysis for unstructured clinical content

CLINICAL_CONCEPT_FIELDS = {
    "ITF": {
        1: {
            SectionType.MOTHER_DETAILS: [
                "U/S findings",
                "Any other maternal condition",
            ],
            SectionType.LABOUR_BIRTH: [
                "Reasons for emergency CS",
                "If yes, describe",
                "Where is the mother currently",
            ],
            SectionType.INFANT_DETAILS: [
                "Reason for referral to NBU",
            ]
        }
    },
    "NAR": {
        1: {
            SectionType.MOTHER_DETAILS: [
                "U/S findings",
                "Maternal history notes",
            ],
            SectionType.INFANT_DETAILS: [
                "Infant presenting problems",
                "Any other important and family / social history?",
            ]
        },
        2: {
            SectionType.FURTHER_EXAMINATION: [
                "Further examination notes",
                "Birth defects description",
                "Neuro",
                "Further examination of Resp / CVS / GIT / GU / Skin / Birth Trauma?"
            ],
            SectionType.SUMMARY: [
                "Summary of presentation and problems",
            ],
            SectionType.DIAGNOSIS: [
                "Others diagnoses (List below)",
            ],
            SectionType.INVESTIGATIONS: [
                "Other investigations",
            ],
            SectionType.ACTION_PLAN: [
                "Action plan",
            ]
        }
    },
}

# ==================== UTILITY MAPPINGS ====================

ENUM_MAPPINGS = {
    # Pos/Neg/Unkn mappings
    "Pos": "Positive",
    "Neg": "Negative",
    "Unkn": "Unknown",
    "Unknown": "Unknown",
    "F": "Female",
    "M": "Male",
    "Indeterminate": "Indeterminate",

    "None": "None",
    "+": "Mild",
    "+++": "Severe",

    # Boolean shortcuts
    "Y": True,
    "N": False,
    "Yes": True,
    "No": False,
    "N/A": None,
}


# ==================== SCHEMA LOADER ====================

def get_form_schema(form_type: str, page_number: int) -> Dict[str, Any]:
    """
    Dynamically load form schema based on form type and page number.

    Args:
        form_type: Form type (ITF, NAR, DSC)
        page_number: Page number (1, 2, etc.)

    Returns:
        Schema dictionary for the specified form and page

    Raises:
        ValueError: If form type or page not supported
        ImportError: If schema file not found

    Example:
        schema = get_form_schema('ITF', 1)
        schema = get_form_schema('NAR', 2)
    """
    form_type_upper = form_type.upper().strip()

    # Validate form type
    valid_forms = [f.value for f in FormType]
    if form_type_upper not in valid_forms:
        raise ValueError(
            f"Unsupported form type: '{form_type}'. "
            f"Supported types: {', '.join(valid_forms)}"
        )

    # Import schema dynamically
    try:
        if form_type_upper == "ITF":
            if page_number == 1:
                from agents.schemas.itf.page_1 import ITF_PAGE_1_SCHEMA
                return ITF_PAGE_1_SCHEMA
            else:
                raise ValueError(f"ITF page {page_number} not supported")

        elif form_type_upper == "NAR":
            if page_number == 1:
                from agents.schemas.nar.page_1 import NAR_PAGE_1_SCHEMA
                return NAR_PAGE_1_SCHEMA
            elif page_number == 2:
                from agents.schemas.nar.page_2 import NAR_PAGE_2_SCHEMA
                return NAR_PAGE_2_SCHEMA
            else:
                raise ValueError(f"NAR page {page_number} not supported")

        '''
        elif form_type_upper == "DSC":
            if page_number == 1:
                from agents.schemas.dsc.page_1 import DSC_PAGE_1_SCHEMA
                return DSC_PAGE_1_SCHEMA
            else:
                raise ValueError(f"DSC page {page_number} not supported")
        '''

    except ImportError as e:
        raise ImportError(
            f"Schema file not found for {form_type_upper} page {page_number}: {e}"
        )


def list_available_schemas() -> Dict[str, List[int]]:
    """
    List all available form schemas.

    Returns:
        dict: Form type -> list of available page numbers

    Example:
        schemas = list_available_schemas()
        # Output: {'ITF': [1, 2], 'NAR': [1, 2], 'DSC': [1]}
    """
    return {
        'ITF': [1],  # Update as more pages are added
        'NAR': [1, 2],  # Update as schemas are created
    }


def validate_schema(schema: Dict[str, Any]) -> bool:
    """
    Validate schema structure.

    Args:
        schema: Schema dictionary to validate

    Returns:
        bool: True if schema is valid

    Raises:
        ValueError: If schema is invalid
    """
    if not isinstance(schema, dict):
        raise ValueError("Schema must be a dictionary")

    if not schema:
        raise ValueError("Schema cannot be empty")

    # Validate each field has required keys
    required_field_keys = {'field_name', 'type', 'required', 'section', 'description'}

    for field_name, field_def in schema.items():
        missing_keys = required_field_keys - set(field_def.keys())
        if missing_keys:
            raise ValueError(
                f"Field '{field_name}' missing required keys: {missing_keys}"
            )

        # Validate type is FieldType enum
        if isinstance(field_def['type'], str):
            try:
                FieldType[field_def['type'].upper()]
            except KeyError:
                raise ValueError(
                    f"Field '{field_name}' has invalid type: {field_def['type']}"
                )
        elif not isinstance(field_def['type'], FieldType):
            raise ValueError(
                f"Field '{field_name}' type must be FieldType enum"
            )

        # Validate section is SectionType enum or string
        if isinstance(field_def['section'], str):
            try:
                SectionType[field_def['section'].upper()]
            except KeyError:
                raise ValueError(
                    f"Field '{field_name}' has invalid section: {field_def['section']}"
                )

    return True


# ==================== CONSTANTS ====================

# Supported form configurations
SUPPORTED_FORMS = {
    'ITF': {
        'name': 'Internal Transfer Form',
        'pages': [1],
        'description': 'Neonatal transfer form with maternal and infant details'
    },
    'NAR': {
        'name': 'Neonatal Admission Record',
        'pages': [1, 2],
        'description': 'Neonatal clinical record and assessment'
    },
}

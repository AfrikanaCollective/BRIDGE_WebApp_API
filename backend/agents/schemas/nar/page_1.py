"""
NAR Page 1 Schema - Neonatal Admission Record (Part 1)
"""

from agents.config import FieldType, SectionType, ClinicalCategory, ENUM_MAPPINGS

# ==================== NAR PAGE 1 SCHEMA ====================

NAR_PAGE_1_SCHEMA = {

    # ==================== A: INFANT DETAILS ====================

    "Date of Admission": {
        "field_name": "Date of Admission",
        "type": FieldType.DATE,
        "format": "DD-MM-YYYY",
        "required": True,
        "section": SectionType.INFANT_DETAILS,
        "clinical_category": ClinicalCategory.ADMINISTRATIVE,
        "is_clinical_concept": False,
        "description": "Date infant admitted"
    },

    "Time baby seen (24 hr clock)": {
        "field_name": "Time baby seen (24 hr clock)",
        "type": FieldType.TIME,
        "format": "HH:MM",
        "required": True,
        "section": SectionType.INFANT_DETAILS,
        "clinical_category": ClinicalCategory.ADMINISTRATIVE,
        "is_clinical_concept": False,
        "description": "Time baby seen"
    },

    "Sex": {
        "field_name": "Sex",
        "type": FieldType.ENUM,
        "required": True,
        "section": SectionType.INFANT_DETAILS,
        "clinical_category": ClinicalCategory.ADMINISTRATIVE,
        "is_clinical_concept": False,
        "values": ["F", "M", "Indeterminate"],
        "enum_mapping": ENUM_MAPPINGS,
        "description": "Baby's sex"
    },

    "DOB": {
        "field_name": "DOB",
        "type": FieldType.DATE,
        "format": "DD-MM-YYYY",
        "required": True,
        "section": SectionType.INFANT_DETAILS,
        "clinical_category": ClinicalCategory.ADMINISTRATIVE,
        "is_clinical_concept": False,
        "description": "Baby's date of birth"
    },

    "Time of birth (24 hr clock)": {
        "field_name": "Time of birth (24 hr clock)",
        "type": FieldType.TIME,
        "format": "HH:MM",
        "required": True,
        "section": SectionType.INFANT_DETAILS,
        "clinical_category": ClinicalCategory.ADMINISTRATIVE,
        "is_clinical_concept": False,
        "description": "Baby's time of birth"
    },

    "Gestation (in weeks)": {
        "field_name": "Gestation (in weeks)",
        "type": FieldType.INTEGER,
        "required": True,
        "section": SectionType.INFANT_DETAILS,
        "clinical_category": ClinicalCategory.HIGH,
        "is_clinical_concept": False,
        "description": "Gestational age at delivery in weeks",
        "validation": {"min": 14, "max": 45},
        "risk_thresholds": {
            "critical_low": 22,  # Periviable
            "high_low": 28,  # Very preterm
            "moderate_low": 32  # Preterm
        }
    },

    "Age (in days)": {
        "field_name": "Age (in days)",
        "type": FieldType.INTEGER,
        "required": True,
        "section": SectionType.INFANT_DETAILS,
        "clinical_category": ClinicalCategory.OBSERVATION,
        "is_clinical_concept": False,
        "description": "Mother's age in years",
        "validation": {"min": 10, "max": 60}
    },

    "Gestation age from?": {
        "field_name": "Gestation age from?",
        "type": FieldType.ENUM,
        "required": True,
        "values": ["U/S", "LMP"],
        "section": SectionType.INFANT_DETAILS,
        "clinical_category": ClinicalCategory.MODERATE,
        "is_clinical_concept": False,
        "description": "Gestational age calculated from",
    },

    "APGAR Score 1M": {
        "field_name": "APGAR Score 1M",
        "type": FieldType.INTEGER,
        "required": True,
        "section": SectionType.INFANT_DETAILS,
        "clinical_category": ClinicalCategory.CRITICAL,
        "is_clinical_concept": False,
        "description": "APGAR score at 1 minute",
        "validation": {"min": 0, "max": 10},
        "risk_thresholds": {
            "critical": 3,
            "high": 5,
            "moderate": 7
        }
    },

    "APGAR Score 5M": {
        "field_name": "APGAR Score 5M",
        "type": FieldType.INTEGER,
        "required": True,
        "section": SectionType.INFANT_DETAILS,
        "clinical_category": ClinicalCategory.CRITICAL,
        "is_clinical_concept": False,
        "description": "APGAR score at 5 minutes",
        "validation": {"min": 0, "max": 10},
        "risk_thresholds": {
            "critical": 3,
            "high": 5,
            "moderate": 7
        }
    },

    "APGAR Score 10M": {
        "field_name": "APGAR Score 10M",
        "type": FieldType.INTEGER,
        "required": True,
        "section": SectionType.INFANT_DETAILS,
        "clinical_category": ClinicalCategory.OBSERVATION,
        "is_clinical_concept": False,
        "description": "APGAR score at 10 minutes",
        "validation": {"min": 0, "max": 10}
    },

    "Delivery": {
        "field_name": "Delivery",
        "type": FieldType.ENUM,
        "required": True,
        "section": SectionType.INFANT_DETAILS,
        "clinical_category": ClinicalCategory.OBSERVATION,
        "is_clinical_concept": False,
        "values": ["SVD", "CS", "VD", "Assisted", "Other"],
        "description": "Mode of delivery"
    },

    "If CS, type": {
        "field_name": "If CS, type",
        "type": FieldType.ENUM,
        "required": False,
        "section": SectionType.INFANT_DETAILS,
        "clinical_category": ClinicalCategory.HIGH,
        "is_clinical_concept": False,
        "values": ["Emergency", "Elective"],
        "description": "Type of caesarean section",
        "risk_flag_value": "Emergency"
    },

    "BVM resus at birth": {
        "field_name": "BVM resus at birth",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.INFANT_DETAILS,
        "clinical_category": ClinicalCategory.HIGH,
        "is_clinical_concept": False,
        "description": "Bag and mask ventilation given",
        "enum_mapping": ENUM_MAPPINGS,
        "risk_flag": True
    },

    "ROM": {
        "field_name": "ROM",
        "type": FieldType.ENUM,
        "required": True,
        "values": ["<18", ">=18h", "Unkn"],
        "section": SectionType.INFANT_DETAILS,
        "clinical_category": ClinicalCategory.HIGH,
        "is_clinical_concept": False,
        "description": "Rupture of membranes (timing in hours)",
        "risk_flag_values": [">=18h"]
    },

    "Multiple delivery": {
        "field_name": "Multiple delivery",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.INFANT_DETAILS,
        "clinical_category": ClinicalCategory.HIGH,
        "is_clinical_concept": False,
        "description": "Multiple deliveries",
        "enum_mapping": ENUM_MAPPINGS,
        "risk_flag": True
    },

    "If YES, number": {
        "field_name": "If YES, number",
        "type": FieldType.INTEGER,
        "required": False,
        "section": SectionType.INFANT_DETAILS,
        "clinical_category": ClinicalCategory.OBSERVATION,
        "is_clinical_concept": False,
        "description": "Number of fetuses in multiple pregnancy",
        "validation": {"min": 2, "max": 10}
    },

    "Born outside facility?": {
        "field_name": "Born outside facility?",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.INFANT_DETAILS,
        "clinical_category": ClinicalCategory.ADMINISTRATIVE,
        "is_clinical_concept": False,
        "description": "If baby is born outside facility",
    },

    "If yes, where?": {
        "field_name": "If yes, where?",
        "type": FieldType.ENUM,
        "required": False,
        "values": ["Home/roadside", "Other facility"],
        "section": SectionType.INFANT_DETAILS,
        "clinical_category": ClinicalCategory.ADMINISTRATIVE,
        "is_clinical_concept": False,
        "description": "If baby is born outside facility",
    },

    # ==================== B: MOTHER DETAILS ====================

    "Age (in years)": {
        "field_name": "Age (in years)",
        "type": FieldType.INTEGER,
        "required": True,
        "section": SectionType.MOTHER_DETAILS,
        "clinical_category": ClinicalCategory.OBSERVATION,
        "is_clinical_concept": False,
        "description": "Mother's age in years",
        "validation": {"min": 10, "max": 60}
    },

    "Parity": {
        "field_name": "Parity",
        "type": FieldType.STRING,
        "required": True,
        "section": SectionType.MOTHER_DETAILS,
        "clinical_category": ClinicalCategory.OBSERVATION,
        "is_clinical_concept": False,
        "description": "Number of prior pregnancies (e.g., 3+0)"
    },

    "EDD": {
        "field_name": "EDD",
        "type": FieldType.DATE,
        "format": "DD-MM-YYYY",
        "required": True,
        "section": SectionType.MOTHER_DETAILS,
        "clinical_category": ClinicalCategory.OBSERVATION,
        "is_clinical_concept": False,
        "description": "Expected date of delivery"
    },

    "ANC no. of visits": {
        "field_name": "ANC no. of visits",
        "type": FieldType.INTEGER,
        "required": False,
        "section": SectionType.MOTHER_DETAILS,
        "clinical_category": ClinicalCategory.MODERATE,
        "is_clinical_concept": False,
        "description": "Number of ANC visits attended",
        "validation": {"min": 0, "max": 20}
    },

    "ANC U/S": {
        "field_name": "ANC U/S",
        "type": FieldType.BOOLEAN,
        "required": False,
        "section": SectionType.MOTHER_DETAILS,
        "clinical_category": ClinicalCategory.MODERATE,
        "is_clinical_concept": False,
        "description": "Antenatal ultrasound performed",
        "enum_mapping": {"Y": True, "N": False}
    },

    "U/S findings": {
        "field_name": "U/S findings",
        "type": FieldType.MULTILINE,
        "required": False,
        "section": SectionType.MOTHER_DETAILS,
        "clinical_category": ClinicalCategory.HIGH,
        "is_clinical_concept": True,
        "description": "Ultrasound findings",
        "keywords": {
            "critical": ["anomaly", "anomalies", "defect", "malformation", "absent", "severe"],
            "high": ["restriction", "iugr", "polyhydramnios", "oligohydramnios", "abnormal"],
            "moderate": ["normal", "adequate", "appropriate"]
        }
    },

    "Blood group": {
        "field_name": "Blood group",
        "type": FieldType.ENUM,
        "required": True,
        "section": SectionType.MOTHER_DETAILS,
        "clinical_category": ClinicalCategory.OBSERVATION,
        "is_clinical_concept": False,
        "values": ["A", "B", "AB", "O", "Unkn"],
        "enum_mapping": {"Unkn": "Unknown"},
        "description": "Mother's blood group"
    },

    "Rhesus": {
        "field_name": "Rhesus",
        "type": FieldType.ENUM,
        "required": True,
        "section": SectionType.MOTHER_DETAILS,
        "clinical_category": ClinicalCategory.OBSERVATION,
        "is_clinical_concept": False,
        "enum_mapping": ENUM_MAPPINGS,
        "description": "Rhesus factor status"
    },

    "VDRL": {
        "field_name": "VDRL",
        "type": FieldType.ENUM,
        "required": True,
        "section": SectionType.MOTHER_DETAILS,
        "clinical_category": ClinicalCategory.HIGH,
        "is_clinical_concept": False,
        "enum_mapping": ENUM_MAPPINGS,
        "description": "Syphilis screening (VDRL test)",
        "risk_flag_value": "Pos"
    },

    "PMTCT status": {
        "field_name": "PMTCT status",
        "type": FieldType.ENUM,
        "required": True,
        "section": SectionType.MOTHER_DETAILS,
        "clinical_category": ClinicalCategory.CRITICAL,
        "is_clinical_concept": False,
        "enum_mapping": ENUM_MAPPINGS,
        "description": "HIV status (Prevention of Mother-to-Child Transmission)",
        "risk_flag_value": "Pos"
    },

    "HTN in pregnancy": {
        "field_name": "HTN in pregnancy",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.MOTHER_DETAILS,
        "clinical_category": ClinicalCategory.HIGH,
        "is_clinical_concept": True,
        "description": "Hypertension in pregnancy",
        "enum_mapping": ENUM_MAPPINGS,
        "risk_flag": True
    },

    "APH": {
        "field_name": "APH",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.MOTHER_DETAILS,
        "clinical_category": ClinicalCategory.CRITICAL,
        "is_clinical_concept": False,
        "description": "Antepartum hemorrhage",
        "enum_mapping": ENUM_MAPPINGS,
        "risk_flag": True
    },

    "Diabetes": {
        "field_name": "Diabetes",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.MOTHER_DETAILS,
        "clinical_category": ClinicalCategory.HIGH,
        "is_clinical_concept": False,
        "description": "Mother has diabetes",
        "enum_mapping": ENUM_MAPPINGS,
        "risk_flag": True
    },

    # ==================== C: MATERNAL HISTORY ====================

    "Maternal history notes": {
        "field_name": "Maternal history notes",
        "type": FieldType.MULTILINE,
        "required": False,
        "section": SectionType.MOTHER_DETAILS,
        "clinical_category": ClinicalCategory.HIGH,
        "is_clinical_concept": True,
        "description": "Maternal history notes",
    },

    # ==================== D: INFANT HISTORY ====================

    "Infant presenting problems": {
        "field_name": "Infant presenting problems",
        "type": FieldType.MULTILINE,
        "required": False,
        "section": SectionType.INFANT_HISTORY,
        "clinical_category": ClinicalCategory.CRITICAL,
        "is_clinical_concept": True,
        "description": "Problems presented by infant",
        "keywords": {
            "critical": ["asphyxia", "seizure", "distress"],
            "high": ["feeding", "breathing"]
        }
    },

    # ==================== E: INFANT_HISTORY ====================

    "Temp": {
        "field_name": "Temp",
        "type": FieldType.FLOAT,
        "required": True,
        "section": SectionType.INFANT_HISTORY,
        "clinical_category": ClinicalCategory.OBSERVATION,
        "is_clinical_concept": False,
        "description": "Temperature in °C",
        "validation": {"min": 28.0, "max": 44.0}
    },

    "Resp Rate": {
        "field_name": "Resp Rate",
        "type": FieldType.STRING,
        "required": True,
        "section": SectionType.INFANT_HISTORY,
        "clinical_category": ClinicalCategory.OBSERVATION,
        "is_clinical_concept": False,
        "description": "Respiratory rate"
    },

    "Pulse": {
        "field_name": "Pulse",
        "type": FieldType.STRING,
        "required": True,
        "section": SectionType.INFANT_HISTORY,
        "clinical_category": ClinicalCategory.OBSERVATION,
        "is_clinical_concept": False,
        "description": "Heart rate (beats per minute)",
    },

    "O2 Sat (%)": {
        "field_name": "O2 Sat (%)",
        "type": FieldType.STRING,
        "required": True,
        "section": SectionType.INFANT_HISTORY,
        "clinical_category": ClinicalCategory.OBSERVATION,
        "is_clinical_concept": False,
        "description": "Oxygen Saturation"
    },

    "Birth Weight (grams)": {
        "field_name": "Birth Weight (grams)",
        "type": FieldType.INTEGER,
        "required": True,
        "section": SectionType.INFANT_HISTORY,
        "clinical_category": ClinicalCategory.HIGH,
        "is_clinical_concept": False,
        "description": "Birth weight in grams",
        "validation": {"min": 500, "max": 8000},
        "risk_thresholds": {
            "critical_low": 1000,
            "high_low": 1500,
            "moderate_low": 2500
        }
    },

    "Weight now (grams)": {
        "field_name": "Weight now (grams)",
        "type": FieldType.INTEGER,
        "required": True,
        "section": SectionType.INFANT_HISTORY,
        "clinical_category": ClinicalCategory.OBSERVATION,
        "is_clinical_concept": False,
        "description": "Current weight in grams",
        "validation": {"min": 500, "max": 8000}
    },

    "Fever": {
        "field_name": "Fever",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.INFANT_HISTORY,
        "clinical_category": ClinicalCategory.HIGH,
        "is_clinical_concept": False,
        "description": "Baby has fever present",
        "enum_mapping": ENUM_MAPPINGS,
        "risk_flag": True
    },

    "Passed meconium/stool": {
        "field_name": "Passed meconium/stool",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.INFANT_HISTORY,
        "clinical_category": ClinicalCategory.HIGH,
        "is_clinical_concept": False,
        "description": "Baby passed meconium stool",
        "enum_mapping": ENUM_MAPPINGS,
        "risk_flag": False
    },

    "Difficulty breathing": {
        "field_name": "Difficulty breathing",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.INFANT_HISTORY,
        "clinical_category": ClinicalCategory.CRITICAL,
        "is_clinical_concept": False,
        "description": "Baby has difficulty breathing",
        "enum_mapping": ENUM_MAPPINGS,
        "risk_flag": True
    },

    "Passed urine": {
        "field_name": "Passed urine",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.INFANT_HISTORY,
        "clinical_category": ClinicalCategory.CRITICAL,
        "is_clinical_concept": False,
        "description": "Baby passed urine",
        "enum_mapping": ENUM_MAPPINGS,
    },

    "Difficulty feeding": {
        "field_name": "Difficulty feeding",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.INFANT_HISTORY,
        "clinical_category": ClinicalCategory.CRITICAL,
        "is_clinical_concept": False,
        "description": "Baby has difficulty feeding",
        "enum_mapping": ENUM_MAPPINGS,
        "risk_flag": True
    },

    "Convulsions / Twitching": {
        "field_name": "Convulsions / Twitching",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.INFANT_HISTORY,
        "clinical_category": ClinicalCategory.CRITICAL,
        "is_clinical_concept": False,
        "description": "Baby has convulsions",
        "enum_mapping": ENUM_MAPPINGS,
        "risk_flag": True
    },

    "Apnoea": {
        "field_name": "Apnoea",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.INFANT_HISTORY,
        "clinical_category": ClinicalCategory.CRITICAL,
        "is_clinical_concept": False,
        "description": "Baby has Apnoea",
        "enum_mapping": ENUM_MAPPINGS,
        "risk_flag": True
    },

    "Reduced / Absent movement": {
        "field_name": "Reduced / Absent movement",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.INFANT_HISTORY,
        "clinical_category": ClinicalCategory.CRITICAL,
        "is_clinical_concept": False,
        "description": "Baby is floppy",
        "enum_mapping": ENUM_MAPPINGS,
        "risk_flag": True
    },

    "Bilious Vomiting": {
        "field_name": "Bilious Vomiting",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.INFANT_HISTORY,
        "clinical_category": ClinicalCategory.CRITICAL,
        "is_clinical_concept": False,
        "description": "Baby has bilious vomiting",
        "enum_mapping": ENUM_MAPPINGS,
        "risk_flag": True
    },

    "Bloody stool": {
        "field_name": "Bloody stool",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.INFANT_HISTORY,
        "clinical_category": ClinicalCategory.CRITICAL,
        "is_clinical_concept": False,
        "description": "Baby has bloody stool",
        "enum_mapping": ENUM_MAPPINGS,
        "risk_flag": True
    },

    "Other history": {
        "field_name": "Any other important and family / social history?",
        "type": FieldType.MULTILINE,
        "required": False,
        "section": SectionType.INFANT_HISTORY,
        "clinical_category": ClinicalCategory.CRITICAL,
        "is_clinical_concept": True,
        "description": "Other family history for the infant",
        "keywords": {
            "critical": ["asphyxia", "seizure", "distress", "LCW", "DIB"],
        }
    },
}

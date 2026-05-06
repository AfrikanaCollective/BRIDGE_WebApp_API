# agents/schemas/nar/page_2.py

"""
NAR Page 2 Schema - Neonatal Admission Record (Page 2)
"""

from agents.config import FieldType, SectionType, ClinicalCategory, ENUM_MAPPINGS

NAR_PAGE_2_SCHEMA = {

    # ==================== F1: GENERAL EXAMINATION ====================

    "Skin": {
        "field_name": "Skin",
        "type": FieldType.ENUM,
        "values": ["Normal", "Bruising", "Rash", "Pustules", "Mottling", "Dry/peeling/Wrinkled"],
        "required": True,
        "section": SectionType.GENERAL_EXAMINATION,
        "clinical_category": ClinicalCategory.OBSERVATION,
        "is_clinical_concept": True,
        "description": "Baby's skin condition",
    },

    "Jaundice": {
        "field_name": "Jaundice",
        "type": FieldType.ENUM,
        "enum_mapping": ENUM_MAPPINGS,
        "required": True,
        "section": SectionType.GENERAL_EXAMINATION,
        "clinical_category": ClinicalCategory.HIGH,
        "is_clinical_concept": True,
        "description": "Level of jaundice",
        "risk_flag_values": ["Severe"]
    },

    "Appearance": {
        "field_name": "Appearance",
        "type": FieldType.ENUM,
        "values": ["Well", "Sick", "Dysmorphic"],
        "required": True,
        "section": SectionType.GENERAL_EXAMINATION,
        "clinical_category": ClinicalCategory.HIGH,
        "is_clinical_concept": True,
        "description": "General appearance of baby",
        "risk_flag_values": ["Sick", "Dysmorphic"]
    },

    "Cry": {
        "field_name": "Cry",
        "type": FieldType.ENUM,
        "values": ["Normal", "Weak/Absent", "Hoarse"],
        "required": True,
        "section": SectionType.GENERAL_EXAMINATION,
        "clinical_category": ClinicalCategory.HIGH,
        "is_clinical_concept": True,
        "description": "Baby's cry",
        "risk_flag_values": ["Weak/Absent"]
    },

    "Crackles": {
        "field_name": "Crackles",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.GENERAL_EXAMINATION,
        "description": "Baby has crackles",
        "clinical_category": ClinicalCategory.HIGH,
        "enum_mapping": ENUM_MAPPINGS,
        "risk_flag": True
    },

    "Grunting": {
        "field_name": "Grunting",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.GENERAL_EXAMINATION,
        "description": "Baby has grunting",
        "clinical_category": ClinicalCategory.CRITICAL,
        "enum_mapping": ENUM_MAPPINGS,
        "risk_flag": True
    },

    "Good bilateral air entry": {
        "field_name": "Good bilateral air entry",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.GENERAL_EXAMINATION,
        "clinical_category": ClinicalCategory.HIGH,
        "enum_mapping": ENUM_MAPPINGS,
        "description": "Air entry in baby's lungs",
        "risk_flag": True
    },

    "Central cyanosis": {
        "field_name": "Central cyanosis",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.GENERAL_EXAMINATION,
        "clinical_category": ClinicalCategory.CRITICAL,
        "enum_mapping": ENUM_MAPPINGS,
        "description": "Cyanosis present in baby's central body",
        "risk_flag": True
    },

    "Lower chest indrawing": {
        "field_name": "Lower chest indrawing",
        "type": FieldType.ENUM,
        "values": ["None", "Mild", "Severe"],
        "required": True,
        "section": SectionType.GENERAL_EXAMINATION,
        "clinical_category": ClinicalCategory.CRITICAL,
        "enum_mapping": {"None": "None", "Mild": "Mild", "Severe": "Severe"},
        "description": "Indrawing of lower chest",
        "risk_flag_values": ["Mild", "Severe"]
    },

    "Xiphoid retraction": {
        "field_name": "Xiphoid retraction",
        "type": FieldType.ENUM,
        "values": ["None", "Mild", "Severe"],
        "required": True,
        "section": SectionType.GENERAL_EXAMINATION,
        "clinical_category": ClinicalCategory.HIGH,
        "enum_mapping": {"None": "None", "Mild": "Mild", "Severe": "Severe"},
        "description": "Retraction of xiphoid process",
        "risk_flag_values": ["Severe"]
    },

    "Intercostal retraction": {
        "field_name": "Intercostal retraction",
        "type": FieldType.ENUM,
        "values": ["None", "Mild", "Severe"],
        "required": True,
        "section": SectionType.GENERAL_EXAMINATION,
        "clinical_category": ClinicalCategory.HIGH,
        "enum_mapping": {"None": "None", "Mild": "Mild", "Severe": "Severe"},
        "description": "Retraction of intercostal muscles",
        "risk_flag_values": ["Severe"]
    },

    "Capillary refill (Sternal)": {
        "field_name": "Capillary refill (Sternal)",
        "type": FieldType.STRING,
        "required": True,
        "section": SectionType.GENERAL_EXAMINATION,
        "clinical_category": ClinicalCategory.HIGH,
        "description": "Capillary refill time at sternal site",
        "validation": {}
    },

    "Pallor/Anaemia": {
        "field_name": "Pallor/Anaemia",
        "type": FieldType.ENUM,
        "values": ["None", "+", "+++"],
        "required": True,
        "section": SectionType.GENERAL_EXAMINATION,
        "clinical_category": ClinicalCategory.HIGH,
        "description": "Pallor or anaemia present in baby",
        "risk_flag_values": ["+", "+++"]
    },

    "Murmur": {
        "field_name": "Murmur",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.GENERAL_EXAMINATION,
        "clinical_category": ClinicalCategory.HIGH,
        "enum_mapping": ENUM_MAPPINGS,
        "description": "Presence of heart murmur",
        "risk_flag": True
    },

    "Bulging fontanelle": {
        "field_name": "Bulging fontanelle",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.GENERAL_EXAMINATION,
        "clinical_category": ClinicalCategory.CRITICAL,
        "enum_mapping": ENUM_MAPPINGS,
        "description": "Does baby have bulging fontanelle",
        "risk_flag": True
    },

    "Irritable": {
        "field_name": "Irritable",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.GENERAL_EXAMINATION,
        "clinical_category": ClinicalCategory.HIGH,
        "enum_mapping": ENUM_MAPPINGS,
        "description": "Baby is irritable",
        "risk_flag": True
    },

    "Tone": {
        "field_name": "Tone",
        "type": FieldType.ENUM,
        "values": ["Normal", "Increased", "Reduced"],
        "required": True,
        "section": SectionType.GENERAL_EXAMINATION,
        "clinical_category": ClinicalCategory.HIGH,
        "description": "Baby's muscle tone",
        "risk_flag_values": ["Reduced"]
    },

    "Distension": {
        "field_name": "Distension",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.GENERAL_EXAMINATION,
        "clinical_category": ClinicalCategory.HIGH,
        "enum_mapping": ENUM_MAPPINGS,
        "description": "Abdominal distension present",
        "risk_flag": True
    },

    "Umbilicus": {
        "field_name": "Umbilicus",
        "type": FieldType.ENUM,
        "values": ["Clean", "Local pus", "Pus + Red skin", "Others"],
        "required": True,
        "section": SectionType.GENERAL_EXAMINATION,
        "clinical_category": ClinicalCategory.HIGH,
        "description": "Condition of the umbilicus",
        "risk_flag_values": ["Local pus", "Pus + Red skin", "Others"]
    },

# ==================== F2: FURTHER EXAMINATION ====================

    "Neuro": {
        "field_name": "Neuro",
        "type": FieldType.MULTILINE,
        "required": False,
        "section": SectionType.FURTHER_EXAMINATION,
        "clinical_category": ClinicalCategory.HIGH,
        "description": "Neurological examination findings",
        "is_clinical_concept": True
    },

    "Further examination of Resp / CVS / GIT / GU / Skin / Birth Trauma?": {
        "field_name": "Further examination of Resp / CVS / GIT / GU / Skin / Birth Trauma?",
        "type": FieldType.MULTILINE,
        "required": False,
        "section": SectionType.FURTHER_EXAMINATION,
        "clinical_category": ClinicalCategory.HIGH,
        "description": "Further examination findings for respiratory, cardiovascular, GIT, GU, skin, and birth trauma",
        "is_clinical_concept": True
    },

    "Birth defects?": {
        "field_name": "Birth defects?",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.FURTHER_EXAMINATION,
        "clinical_category": ClinicalCategory.CRITICAL,
        "enum_mapping": ENUM_MAPPINGS,
        "description": "Birth defects present in baby",
        "risk_flag": True
    },

    "Major GI abnormality": {
        "field_name": "Major GI abnormality",
        "type": FieldType.BOOLEAN,
        "enum_mapping": ENUM_MAPPINGS,
        "required": False,
        "section": SectionType.FURTHER_EXAMINATION,
        "clinical_category": ClinicalCategory.CRITICAL,
        "description": "Major gastrointestinal abnormality",
        "risk_flag": True
    },

    "Hydrocephalus": {
        "field_name": "Hydrocephalus",
        "type": FieldType.BOOLEAN,
        "enum_mapping": ENUM_MAPPINGS,
        "required": False,
        "section": SectionType.FURTHER_EXAMINATION,
        "clinical_category": ClinicalCategory.CRITICAL,
        "description": "Hydrocephalus present",
        "risk_flag": True
    },

    "Cleft lip/palate": {
        "field_name": "Cleft lip/palate",
        "type": FieldType.BOOLEAN,
        "enum_mapping": ENUM_MAPPINGS,
        "required": False,
        "section": SectionType.FURTHER_EXAMINATION,
        "clinical_category": ClinicalCategory.CRITICAL,
        "description": "Cleft lip or palate present",
        "risk_flag": True
    },

    "Microcephaly": {
        "field_name": "Microcephaly",
        "type": FieldType.BOOLEAN,
        "enum_mapping": ENUM_MAPPINGS,
        "required": False,
        "section": SectionType.FURTHER_EXAMINATION,
        "clinical_category": ClinicalCategory.CRITICAL,
        "description": "Microcephaly present",
        "risk_flag": True
    },

    "Neural tube defects": {
        "field_name": "Neural tube defects",
        "type": FieldType.BOOLEAN,
        "enum_mapping": ENUM_MAPPINGS,
        "required": False,
        "section": SectionType.FURTHER_EXAMINATION,
        "clinical_category": ClinicalCategory.CRITICAL,
        "description": "Neural tube defects present",
        "risk_flag": True
    },

    "Spina bifida": {
        "field_name": "Spina bifida",
        "type": FieldType.BOOLEAN,
        "enum_mapping": ENUM_MAPPINGS,
        "required": False,
        "section": SectionType.FURTHER_EXAMINATION,
        "clinical_category": ClinicalCategory.CRITICAL,
        "description": "Spina bifida present",
        "risk_flag": True
    },

    "Limb abnormalities": {
        "field_name": "Limb abnormalities",
        "type": FieldType.BOOLEAN,
        "enum_mapping": ENUM_MAPPINGS,
        "required": False,
        "section": SectionType.FURTHER_EXAMINATION,
        "clinical_category": ClinicalCategory.CRITICAL,
        "description": "Limb abnormalities present",
        "risk_flag": True
    },

    "Birth injury/abnormalities": {
        "field_name": "Birth injury/abnormalities",
        "type": FieldType.BOOLEAN,
        "enum_mapping": ENUM_MAPPINGS,
        "required": False,
        "section": SectionType.FURTHER_EXAMINATION,
        "clinical_category": ClinicalCategory.CRITICAL,
        "description": "Birth injury or other abnormalities",
        "risk_flag": True
    },

    # ==================== G: SUMMARY ====================

    "Summary of presentation and problems": {
        "field_name": "Summary of presentation and problems",
        "type": FieldType.MULTILINE,
        "required": False,
        "section": SectionType.SUMMARY,
        "clinical_category": ClinicalCategory.CRITICAL,
        "description": "Summary of baby's presentation and problems",
        "is_clinical_concept": True
    },

    # ==================== H: INVESTIGATIONS ====================

    "Investigations ordered": {
        "field_name": "Investigations ordered",
        "type": FieldType.MULTILINE,
        "required": False,
        "section": SectionType.INVESTIGATIONS,
        "clinical_category": ClinicalCategory.HIGH,
        "description": "Investigations ordered for the baby"
    },

    "Bilirubin": {
        "field_name": "Bilirubin",
        "type": FieldType.MULTILINE,
        "required": False,
        "section": SectionType.INVESTIGATIONS,
        "clinical_category": ClinicalCategory.HIGH,
        "description": "Bilirubin measured or needed"
    },

    "RBS": {
        "field_name": "RBS",
        "type": FieldType.MULTILINE,
        "required": False,
        "section": SectionType.INVESTIGATIONS,
        "clinical_category": ClinicalCategory.HIGH,
        "description": "Random blood sugar measured or needed"
    },

    # ==================== I: DIAGNOSES ====================

    "Prematurity": {
        "field_name": "Prematurity",
        "type": FieldType.BOOLEAN,
        "enum_mapping": ENUM_MAPPINGS,
        "required": False,
        "section": SectionType.DIAGNOSIS,
        "clinical_category": ClinicalCategory.CRITICAL,
        "description": "Prematurity diagnosis",
        "risk_flag": True
    },

    "LBW": {
        "field_name": "LBW",
        "type": FieldType.BOOLEAN,
        "enum_mapping": ENUM_MAPPINGS,
        "required": False,
        "section": SectionType.DIAGNOSIS,
        "clinical_category": ClinicalCategory.HIGH,
        "description": "Low birth weight diagnosis",
        "risk_flag": True
    },

    "Birth Asphyxia": {
        "field_name": "Birth Asphyxia",
        "type": FieldType.BOOLEAN,
        "enum_mapping": ENUM_MAPPINGS,
        "required": False,
        "section": SectionType.DIAGNOSIS,
        "clinical_category": ClinicalCategory.CRITICAL,
        "description": "Birth asphyxia diagnosis",
        "risk_flag": True
    },

    "Newborn RDS": {
        "field_name": "Newborn RDS",
        "type": FieldType.BOOLEAN,
        "enum_mapping": ENUM_MAPPINGS,
        "required": False,
        "section": SectionType.DIAGNOSIS,
        "clinical_category": ClinicalCategory.CRITICAL,
        "description": "Respiratory distress syndrome diagnosis",
        "risk_flag": True
    },

    "Neonatal Sepsis": {
        "field_name": "Neonatal Sepsis",
        "type": FieldType.BOOLEAN,
        "values": ["N/A", "Yes", "No"],
        "required": False,
        "section": SectionType.DIAGNOSIS,
        "clinical_category": ClinicalCategory.CRITICAL,
        "description": "Neonatal sepsis diagnosis",
        "risk_flag": True
    },

    "Meconium Aspiration": {
        "field_name": "Meconium Aspiration",
        "type": FieldType.BOOLEAN,
        "enum_mapping": ENUM_MAPPINGS,
        "required": False,
        "section": SectionType.DIAGNOSIS,
        "clinical_category": ClinicalCategory.CRITICAL,
        "description": "Meconium aspiration syndrome diagnosis",
        "risk_flag": True
    },

    "Meningitis": {
        "field_name": "Meningitis",
        "type": FieldType.BOOLEAN,
        "enum_mapping": ENUM_MAPPINGS,
        "required": False,
        "section": SectionType.DIAGNOSIS,
        "clinical_category": ClinicalCategory.CRITICAL,
        "description": "Meningitis diagnosis",
        "risk_flag": True
    },

    "Congenital Anomaly": {
        "field_name": "Congenital Anomaly",
        "type": FieldType.BOOLEAN,
        "enum_mapping": ENUM_MAPPINGS,
        "required": False,
        "section": SectionType.DIAGNOSIS,
        "clinical_category": ClinicalCategory.CRITICAL,
        "description": "Congenital anomaly diagnosis",
        "risk_flag": True
    },

    "Multiple Gestation": {
        "field_name": "Multiple Gestation",
        "type": FieldType.BOOLEAN,
        "enum_mapping": ENUM_MAPPINGS,
        "required": False,
        "section": SectionType.DIAGNOSIS,
        "clinical_category": ClinicalCategory.HIGH,
        "description": "Multiple gestation (twins, triplets, etc.)",
        "risk_flag": True
    },

    "Others diagnoses (List below)": {
        "field_name": "Others diagnoses (List below)",
        "type": FieldType.MULTILINE,
        "required": True,
        "section": SectionType.DIAGNOSIS,
        "clinical_category": ClinicalCategory.HIGH,
        "description": "Other diagnoses not listed above",
        "is_clinical_concept": True
    },

    # ==================== J: IMMUNISATIONS & FEEDING ====================

    "Vit K & TEO": {
        "field_name": "Vit K & TEO",
        "type": FieldType.BOOLEAN,
        "enum_mapping": ENUM_MAPPINGS,
        "required": True,
        "section": SectionType.INTERVENTIONS,
        "clinical_category": ClinicalCategory.OBSERVATION,
        "description": "Vitamin K and topical eye ointment given"
    },

    "BCG": {
        "field_name": "BCG",
        "type": FieldType.BOOLEAN,
        "enum_mapping": ENUM_MAPPINGS,
        "required": True,
        "section": SectionType.INTERVENTIONS,
        "clinical_category": ClinicalCategory.OBSERVATION,
        "description": "BCG vaccination given"
    },

    "OPV": {
        "field_name": "OPV",
        "type": FieldType.BOOLEAN,
        "enum_mapping": ENUM_MAPPINGS,
        "required": True,
        "section": SectionType.INTERVENTIONS,
        "clinical_category": ClinicalCategory.OBSERVATION,
        "description": "OPV (polio) vaccination given"
    },

    "Prophylaxis for PMTCT": {
        "field_name": "Prophylaxis for PMTCT",
        "type": FieldType.BOOLEAN,
        "enum_mapping": ENUM_MAPPINGS,
        "required": True,
        "section": SectionType.INTERVENTIONS,
        "clinical_category": ClinicalCategory.OBSERVATION,
        "description": "Prophylaxis for prevention of mother-to-child transmission"
    },

    # ==================== J: TREATMENT & INTERVENTIONS ====================

    "Transfusion": {
        "field_name": "Transfusion",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.INTERVENTIONS,
        "clinical_category": ClinicalCategory.CRITICAL,
        "enum_mapping": ENUM_MAPPINGS,
        "description": "Blood transfusion given",
        "risk_flag": True
    },

    "Antibiotics": {
        "field_name": "Antibiotics",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.INTERVENTIONS,
        "clinical_category": ClinicalCategory.CRITICAL,
        "enum_mapping": ENUM_MAPPINGS,
        "description": "Antibiotic therapy given"
    },

    "Caffeine Citrate": {
        "field_name": "Caffeine Citrate",
        "type": FieldType.ENUM,
        "values": ["N/A", "Yes", "No"],
        "required": True,
        "section": SectionType.INTERVENTIONS,
        "clinical_category": ClinicalCategory.HIGH,
        "description": "Caffeine citrate given for apnoea"
    },

    "Chlorhexidine": {
        "field_name": "Chlorhexidine",
        "type": FieldType.ENUM,
        "values": ["N/A", "Yes", "No"],
        "required": True,
        "section": SectionType.INTERVENTIONS,
        "clinical_category": ClinicalCategory.OBSERVATION,
        "description": "Chlorhexidine given for cord care"
    },

    "Phototherapy": {
        "field_name": "Phototherapy",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.INTERVENTIONS,
        "clinical_category": ClinicalCategory.HIGH,
        "enum_mapping": ENUM_MAPPINGS,
        "description": "Phototherapy given for jaundice"
    },

    "Nutrition/feeds": {
        "field_name": "Nutrition/feeds",
        "type": FieldType.ENUM,
        "values": ["N/A", "Yes", "No"],
        "required": True,
        "section": SectionType.INTERVENTIONS,
        "clinical_category": ClinicalCategory.OBSERVATION,
        "description": "Feeding/nutrition support"
    },

    "Oxygen": {
        "field_name": "Oxygen",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.INTERVENTIONS,
        "clinical_category": ClinicalCategory.CRITICAL,
        "enum_mapping": ENUM_MAPPINGS,
        "description": "Oxygen therapy given",
        "risk_flag": True
    },

    "KMC": {
        "field_name": "KMC",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.INTERVENTIONS,
        "clinical_category": ClinicalCategory.OBSERVATION,
        "enum_mapping": ENUM_MAPPINGS,
        "description": "Kangaroo mother care provided"
    },

    "CPAP": {
        "field_name": "CPAP",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.INTERVENTIONS,
        "clinical_category": ClinicalCategory.CRITICAL,
        "enum_mapping":ENUM_MAPPINGS,
        "description": "CPAP therapy given",
        "risk_flag": True
    },

    "Incubator/ Keep warm": {
        "field_name": "Incubator/ Keep warm",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.INTERVENTIONS,
        "clinical_category": ClinicalCategory.OBSERVATION,
        "enum_mapping": ENUM_MAPPINGS,
        "description": "Incubator or warm environment provided"
    },

    "IV Fluids": {
        "field_name": "IV Fluids",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.INTERVENTIONS,
        "clinical_category": ClinicalCategory.HIGH,
        "enum_mapping": ENUM_MAPPINGS,
        "description": "Intravenous fluids given"
    },

    "Surfactant": {
        "field_name": "Surfactant",
        "type": FieldType.BOOLEAN,
        "required": True,
        "section": SectionType.INTERVENTIONS,
        "clinical_category": ClinicalCategory.CRITICAL,
        "enum_mapping": ENUM_MAPPINGS,
        "description": "Surfactant therapy given",
        "risk_flag": True
    },

    # ==================== K: ACTION PLAN ====================

    "Action plan": {
        "field_name": "Action plan",
        "type": FieldType.MULTILINE,
        "required": False,
        "section": SectionType.ACTION_PLAN,
        "clinical_category": ClinicalCategory.CRITICAL,
        "description": "Action plan for baby's management",
        "is_clinical_concept": True
    },

}

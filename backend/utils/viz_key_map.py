# backend/utils/viz_key_map.py
"""
Key-renaming map for the visualisation layer.

VIZ_KEY_MAP maps  viz_short_key → original_patient_summary_key  per form type.
INVERTED_VIZ_KEY_MAP (pre-computed at import time) maps the reverse direction
and is what VizSyncService uses at runtime to rename fields efficiently.

Merge order when flattening ITF + NAR into a single document:
  ITF fields are written first; NAR fields overwrite any shared key.
  Fields not present in the map are passed through under their original name.
"""

VIZ_KEY_MAP: dict[str, dict[str, str]] = {
    "ITF": {
        "abnormal_placenta": "placental_abnormalities",
        "anc_visits": "number_of_anc_visits_attended",
        "antenatal_steroids": "corticosteroids_given",
        "attended_anc": "mother_attended_antenatal_care",
        "baby_age": "neonatal_age",
        "baby_from": "location_baby_originated_from",
        "birth_date": "baby's_date_of_birth",
        "birth_weight": "birth_weight_in_grams",
        "blood_group": "mother's_blood_group",
        "chest_compressions": "chest_compressions_performed",
        "date_estimated_delivery_date": "expected_date_of_delivery",
        "date_last_menstrual_period": "last_menstrual_period",
        "delivery_type": "mode_of_delivery",
        "fetal_distress": "fetal_distress_during_labour",
        "gestation_in_weeks": "gestational_age_at_delivery_in_weeks",
        "given_bcg": "bcg_vaccine",
        "given_chlorhexidine": "chlorhexidine_cord_care",
        "given_teo": "thermal_care",
        "given_vitamin_k": "vitamin_k_prophylaxis_given",
        "gravida": "total_number_of_pregnancies",
        "had_cs": "type_of_caesarean_section",
        "has_fever": "maternal_fever_present",
        "multiple_pregnancy": "multiple_pregnancy",
        "mum_age_in_years": "mother's_age_in_years",
        "mum_had_antepartum_haemorrhage": "antepartum_hemorrhage",
        "mum_had_eclampsia": "eclampsia",
        "mum_had_hep_b": "hepatitis_b_vaccine",
        "mum_had_pre_eclampsia": "pre-eclampsia",
        "mum_had_vdrl": "syphilis_screening_vdrl_test",
        "mum_on_arvs": "mother_on_antiretroviral_therapy",
        "mum_pmtct_status": "hiv_status_prevention_of_mother-to-child_transmission",
        "parity_abortions": "number_of_stillbirths/deaths",
        "parity_live": "number_of_live_births",
        "pulse_oximetry": "oxygen_saturation",
        "passed_meconium": "meconium-stained_amniotic_fluid",
        "placenta_complete": "placenta_completely_delivered",
        "prescribed_cpap": "cpap_support",
        "prescribed_opv": "oral_polio_vaccine",
        "prescribed_oxygen": "supplemental_oxygen",
        "pulse_rate": "heart_rate_beats_per_minute",
        "rapture_of_membrane": "rupture_of_membranes_timing_eg_>18h",
        "respiratory_rate": "respiratory_rate",
        "rhesus": "rhesus_factor_status",
        "sex": "baby's_sex",
        "temparature": "temperature_in_°c",
        "was_resuscitated": "bag_and_mask_ventilation_given",
        "weight": "current_weight_in_grams",
    },
    "NAR": {
        "anc_visits": "number_of_anc_visits_attended",
        "birth_date": "baby's_date_of_birth",
        "birth_weight": "birth_weight_in_grams",
        "blood_group": "mother's_blood_group",
        "baby_age_in_days": "baby's_age_in_days",
        "born_before_arrival": "is_baby_born_outside_facility",
        "mum_given_HBIG_treatment": "mother_given_hbig_treatment",
        "mum_on_arvs": "mother_on_arvs",
        "head_circumference": "head_circumference_in_cm",
        "length": "length_in_cm",
        "parity_abortions": "number_of_stillbirths/deaths",
        "parity_live": "number_of_live_births",
        "date_estimated_delivery_date": "expected_date_of_delivery",
        "delivery_type": "mode_of_delivery",
        "gestation_in_weeks": "gestational_age_at_delivery_in_weeks",
        "had_cs": "type_of_caesarean_section",
        "has_apnoea": "baby_has_apnoea",
        "has_convulsions": "baby_has_convulsions",
        "has_diarhoea": "baby_has_bloody_stool",
        "has_difficulty_breathing": "baby_has_difficulty_breathing",
        "has_difficulty_feeding": "baby_has_difficulty_feeding",
        "has_fever": "baby_has_fever_present",
        "has_vomiting": "baby_has_bilious_vomiting",
        "is_floppy": "baby_is_floppy",
        "is_multiple_delivery": "multiple_deliveries",
        "multiple_delivery_num": "number_of_fetuses_in_multiple_pregnancy",
        "mum_age_in_years": "mother's_age_in_years",
        "mum_had_antepartum_haemorrhage": "antepartum_hemorrhage",
        "mum_had_vdrl": "syphilis_screening_vdrl_test",
        "passed_meconium": "baby_passed_meconium_stool",
        "passed_urine": "baby_passed_urine",
        "prolonged_labour": "mother_had_prolonged_labour",
        "pulse_oximetry": "oxygen_saturation",
        "pulse_rate": "heart_rate_beats_per_minute",
        "rapture_of_membrane": "rupture_of_membranes_timing_in_hours",
        "respiratory_rate": "respiratory_rate",
        "rhesus": "rhesus_factor_status",
        "sex": "baby's_sex",
        "temparature": "temperature_in_°c",
        "time_birth": "baby's_time_of_birth",
        "time_seen": "time_baby_seen",
        "was_resuscitated": "bag_and_mask_ventilation_given",
        "weight": "current_weight_in_grams",
        "appearance": "general_appearance_of_baby",
        "capillary_refill_in_seconds": "capillary_refill_time_at_sternal_site",
        "chest_indrawing": "indrawing_of_lower_chest",
        "cry": "baby's_cry",
        "given_bcg": "bcg_vaccination_given",
        "given_chlorhexidine": "chlorhexidine_given_for_cord_care",
        "given_prophylaxis_pmtct": "prophylaxis_for_prevention_of_mother-to-child_transmission",
        "given_vitamin_k": "vitamin_k_and_topical_eye_ointment_given",
        "has_birth_defects": "birth_defects_present_in_baby",
        "has_bulging_fontanelle": "does_baby_have_bulging_fontanelle",
        "has_central_cyanosis": "cyanosis_present_in_baby's_central_body",
        "has_crackles": "baby_has_crackles",
        "has_good_air_entry": "air_entry_in_baby's_lungs",
        "has_grunting": "baby_has_grunting",
        "has_murmur": "presence_of_heart_murmur",
        "intercostal_retraction": "retraction_of_intercostal_muscles",
        "is_distended": "abdominal_distension_present",
        "is_irritable": "baby_is_irritable",
        "prescribed_antibiotics": "antibiotic_therapy_given",
        "prescribed_caffeine_citrate": "caffeine_citrate_given_for_apnoea",
        "prescribed_cpap": "cpap_therapy_given",
        "prescribed_feeds": "feeding/nutrition_support",
        "prescribed_incubator": "incubator_or_warm_environment_provided",
        "prescribed_iv_fluids": "intravenous_fluids_given",
        "prescribed_kmc": "kangaroo_mother_care_provided",
        "prescribed_opv": "opv_polio_vaccination_given",
        "prescribed_oxygen": "oxygen_therapy_given",
        "prescribed_phototherapy": "phototherapy_given_for_jaundice",
        "prescribed_surfactant": "surfactant_therapy_given",
        "prescribed_transfusion": "blood_transfusion_given",
        "skin": "baby's_skin_condition",
        "tone": "baby's_muscle_tone",
        "umbilicus": "condition_of_the_umbilicus",
        "xiphoid_retraction": "retraction_of_xiphoid_process",
    },
}

# original_key → viz_key, built once at import time
INVERTED_VIZ_KEY_MAP: dict[str, dict[str, str]] = {
    form_type: {original: viz for viz, original in form_map.items()}
    for form_type, form_map in VIZ_KEY_MAP.items()
}

# Viz keys whose values must be coerced to int or float after renaming.
# Whole-number values are stored as int; values with a decimal part as float.
NUMERIC_VIZ_KEYS: frozenset[str] = frozenset({
    "pulse_rate",
    "pulse_oximetry",
    "temparature",
    "respiratory_rate",
})

# Viz keys whose string values 'True'/'False' must be coerced to bool.
# Only the exact strings 'True' and 'False' are converted; other values
# (e.g. 'Unknown') are left unchanged.
BOOLEAN_VIZ_KEYS: frozenset[str] = frozenset({
    "mum_given_HBIG_treatment",
    "chest_indrawing",
    "mother_on_antibiotics",
    "mother_on_tb_treatment",
})

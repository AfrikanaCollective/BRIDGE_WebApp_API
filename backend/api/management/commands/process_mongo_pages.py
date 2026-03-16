import re
import numpy as np
import logging, logging.config
from collections import defaultdict
from django.core.management.base import BaseCommand

from django.conf import settings
from api.models import PageImage
from api.services.mongo_mapping_loader import mongo_pages

from api.mongo_artefacts import (
    get_mongo_connection,
    PaperRecordPageCollection
)

logging.config.dictConfig(settings.LOGGING)

combine_rules = {
    "temp": lambda vals: f"{''.join(vals[:-1])}.{vals[-1]}" if len(vals) > 1 else "".join(vals),
    "time_birth": lambda vals: f"{''.join(vals[:2])}:{''.join(vals[2:])}" if len(vals) > 3 else "".join(vals),
    "time_seen": lambda vals: f"{''.join(vals[:2])}:{''.join(vals[2:])}" if len(vals) > 3 else "".join(vals),
    "time_followup": lambda vals: f"{''.join(vals[:2])}:{''.join(vals[2:])}" if len(vals) > 3 else "".join(vals),
    "date_admission": lambda vals: f"{''.join(vals[:2])}-{''.join(vals[2:4])}-{''.join(vals[4:])}" if len(vals) > 5 else "".join(vals),
    "date_lmp": lambda vals: f"{''.join(vals[:2])}-{''.join(vals[2:4])}-{''.join(vals[4:])}" if len(vals) > 5 else "".join(vals),
    "date_birth": lambda vals: f"{''.join(vals[:2])}-{''.join(vals[2:4])}-{''.join(vals[4:])}" if len(vals) > 5 else "".join(vals),
    "date_edd": lambda vals: f"{''.join(vals[:2])}-{''.join(vals[2:4])}-{''.join(vals[4:])}" if len(vals) > 5 else "".join(vals),
    "date_discharge": lambda vals: f"{''.join(vals[:2])}-{''.join(vals[2:4])}-{''.join(vals[4:])}" if len(vals) > 5 else "".join(vals),
    "date_followup": lambda vals: f"{''.join(vals[:2])}-{''.join(vals[2:4])}-{''.join(vals[4:])}" if len(vals) > 5 else "".join(vals)
}

rename_map = {
    "date_edd": "date_estimated_delivery_date",
    "date_admission": "date",
    "gestation" : "gestation_in_weeks",
    "date_birth" : "birth_date",
    "date_lmp": "date_last_menstrual_period",
    "age_days": "baby_age_in_days",
    "bvm_resuscitation": "was_resuscitated",
    "rom": "rapture_of_membrane",
    'cs': "had_cs",
    'bba': 'born_before_arrival',
    'bba_type': 'born_where',
    'multiple_delivery': 'is_multiple_delivery',   
    'age_years': 'mum_age_in_years',     
    'anc_us': 'mum_has_anc_ultrasound',
    'anc_us_trimester': 'anc_ultrasound_trimester',
    'hep_b': 'mum_had_hep_b',
    'anti_d': 'given_anti_D_medication',
    'pmtct': 'mum_pmtct_status',
    'mum_arvs': 'mum_on_arvs',
    'mom_arvs': 'mum_on_arvs',
    'hiv_arvs': 'prescribed_pmtct_arvs',
    'vdrl': 'mum_had_vdrl', 
    'hepb': 'mum_had_hepatitis_b',
    'hepb_ig_given': 'mum_given_HBIG_treatment',
    'htn_pregnancy' : 'mum_had_hypertension_in_pregnancy',
    'pre_eclampsia' : 'mum_had_pre_eclampsia',
    'eclampsia' : 'mum_had_eclampsia',
    'aph': 'mum_had_antepartum_haemorrhage',
    'treated_tb': 'mum_treated_for_tb', 
    'diabetes': 'mum_had_diabetes', 
    'prolonged_stage2': 'prolonged_labour', 
    'delivery': 'delivery_type',
    'head_circumfrence': 'head_circumference', 
    'temp': 'temparature', 
    'resp_rate': 'respiratory_rate', 
    'pulse_rate': 'pulse_rate', 
    'pulse_oximetry': 'pulse_oximetry', 
    'weight_now': 'weight', 
    'fever': 'has_fever', 
    'meconium': 'passed_meconium', 
    'difficulty_breathing': 'has_difficulty_breathing', 
    'urine': 'passed_urine', 
    'difficulty_feeding': 'has_difficulty_feeding', 
    'convulsions': 'has_convulsions', 
    'apnoea': 'has_apnoea', 
    'diarhoea': 'has_diarhoea',
    "floppy": "is_floppy",
    "vomiting": "has_vomiting",
    'crackles': 'has_crackles', 
    'grunting': 'has_grunting', 
    'good_air_entry': 'has_good_air_entry', 
    'central_cyanosis': 'has_central_cyanosis', 
    'capillary_refill': 'capillary_refill_in_seconds', 
    'birth_defects': 'has_birth_defects', 
    'murmur': 'has_murmur', 
    'bulging_fontanelle': 'has_bulging_fontanelle', 
    'irritable': 'is_irritable',  
    'distension': 'is_distended', 
    'rbs': 'rbs_measured', 
    'bilirubin': 'given_bilirubin',  
    'vitamin_k_teo': 'given_vitamin_k', 
    'vitamin_k': 'given_vitamin_k',
    'prophylaxis_pmtct': 'given_prophylaxis_pmtct', 
    'bcg': 'given_bcg', 
    'teo': 'given_teo', 
    'chlorhexidine': 'given_chlorhexidine'
}

interventions = [
    'kmc', 'incubator', 'transfusion', 'phototherapy', 
    'cpap', 'iv_fluids', 'antibiotics', 'feeds', 'opv',  
    'surfactant', 'caffeine_citrate', 'oxygen'
]

diagnoses_list = [
    'prematurity', 'preterm', 'jaundice_adx', 'lbw', 'meconium_aspiration', 
    'asphyxia', 'meningitis', 'rds', 'congenital_anomaly', 'sepsis', 'anaemia',
    'multiple_gestation'
]

follow_up_clinics = [
    "follow_up_clinic_cwc", "follow_up_clinic_popc", "follow_up_clinic_kmc",
    "follow_up_clinic_ot", "follow_up_clinic_pmtct", "follow_up_clinic_other"
]

def convert_nans(obj):
    if isinstance(obj, dict):
        return {k: convert_nans(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_nans(x) for x in obj]
    elif isinstance(obj, float) and np.isnan(obj):
        return None
    else:
        return obj
    
def extract_numeric_suffix(text):
    # Extract the last number in the string, default to 0 if none
    match = re.search(r'(\d+)$', text)
    return int(match.group(1)) if match else 0

def rename_keys(data_dict, rename_map):
    return {rename_map.get(k, k): v for k, v in data_dict.items()}

def combine_values(records, form_type):

    grouped = defaultdict(list)

    for item in records:
        if item['variable'].endswith('_combined'):
            continue

        grouped[item['variable']].append(item)

    result = {}

    skip_cols = ['time_sign_units', 'time_sign', 'date_sign', 'birth_defects_type', 
                 'rbs_measure', 'serum_bilirubin', 'anc_us_trimester', 
                 'steroid_doses', 'stage_two_minutes', 'stage_one_hours', 'date_transfer',
                 'time_transfer', 'meconium_grade', 'time_labour', 'resuscitation_duration',
                 'baby_age_units', 'pregnancy', 'hie', 'hb', 'outcome_alive', 'explained_danger_signs_alt']
    
    special_checkbox_vars = [
        "explained_coord_care", "explained_danger_signs",  "explained_breastfeeding", 
        "explained_rop_followup", "polio_vaccine_given", "feed_ebm_only",		
        "feed_breastmilk_only",	"feed_formula_only", "feed_formula_breastmilk"
    ]

    if form_type in ["NAR"]:    
        result["primary_admission_diagnosis"] = "";
        result["secondary_admission_diagnosis"] = "";

    if form_type in ["DSC"]:    
        result["primary_discharge_diagnosis"] = "";
        result["secondary_discharge_diagnosis"] = "";
    
    if form_type in ["DSC"]: 
        result["follow_up_clinic"] = "";
    
    for var, items in grouped.items():

        if var in skip_cols:
            continue        

        roi_type = items[0]['roi_type']  # assume same type for same variable
        if roi_type == 'character':
            # Sort by numeric suffix and combine as string
            sorted_items = sorted(items, key=lambda x: extract_numeric_suffix(x['id']))
            values = [str(i.get("value", '@')) for i in sorted_items]

            # Apply custom rule if exists
            if var in combine_rules:
                combined = combine_rules[var](values)
            else:
                combined = "".join(values)

            if re.fullmatch(r'[\?\@\.\-\+\\/:]+', combined):  # Matches one or more @
                result[var] = np.nan
            else:
                cleaned = re.sub(r"^@|@$", "", combined)
                result[var] = cleaned

            
        elif roi_type == 'checkbox':

            if var in diagnoses_list:
                diagnoses_selected = [i for i in items if i['value'] == 1]

                if len(diagnoses_selected) == 1:

                    # Return difference of id and variable name
                    id_value = diagnoses_selected[0]['id']
                    var_name = diagnoses_selected[0]['variable']
                    # Remove the variable part and leading underscore if present
                    diff = id_value.replace(var_name, '', 1).lstrip('_')

                    if diff in ['primary']:
                        if form_type in ["NAR"]:
                            result["primary_admission_diagnosis"] += var + "; "
                        if form_type in ["DSC"]:
                            result["primary_discharge_diagnosis"] += var + "; "

                    if diff in ['secondary']:
                        if form_type in ["NAR"]:
                            result["secondary_admission_diagnosis"] += var + "; "
                        if form_type in ["DSC"]:
                            result["secondary_discharge_diagnosis"] += var + "; "

            
            elif var == "follow_up_clinic":

                clinic_selected = [i for i in items if i['value'] == 1]

                if len(clinic_selected) > 0:

                    for clinic in clinic_selected:

                        # Return difference of id and variable name
                        id_value = clinic['id']
                        var_name = clinic['variable']
                        # Remove the variable part and leading underscore if present
                        diff = id_value.replace(var_name, '', 1).lstrip('_')

                        result[var] += diff + "; "

            else:   

                if ((var in interventions) and (form_type in ["NAR", "ITF"])): 
                    var = "prescribed_" + var    

                if ((var in interventions) and (form_type in ["DSC"])): 
                    var = "given_" + var         

                ones = [i for i in items if i.get('value') == 1]
                if len(ones) == 0:

                    if var in special_checkbox_vars:
                        result[var] = False
                    else:
                        result[var] = np.nan

                elif len(ones) == 1 and var not in special_checkbox_vars:
                    # Return difference of id and variable name
                    id_value = ones[0]['id']
                    var_name = ones[0]['variable']
                    # Remove the variable part and leading underscore if present
                    diff = id_value.replace(var_name, '', 1).lstrip('_')
                    
                    if diff in ['no', 'negative'] and var != 'rhesus':
                        result[var] = False
                    elif diff in ['yes', 'positive'] and var != 'rhesus':
                        result[var] = True
                    else:
                        result[var] = diff  # Keep raw string if not recognized

                elif len(ones) == 1 and var in special_checkbox_vars:
                    result[var] = True

                else:
                    result[var] = '?'

    if form_type in ["NAR"]:
        if result["primary_admission_diagnosis"] == "":
            result["primary_admission_diagnosis"] = np.nan

        if result["secondary_admission_diagnosis"] == "":
            result["secondary_admission_diagnosis"] = np.nan
    
    if form_type in ["DSC"]:
        if result["primary_discharge_diagnosis"] == "":
            result["primary_discharge_diagnosis"] = np.nan

        if result["secondary_discharge_diagnosis"] == "":
            result["secondary_discharge_diagnosis"] = np.nan

    if form_type in ["DSC"]: 
        if result["follow_up_clinic"] == "":
            result["follow_up_clinic"] = np.nan       

    human_readable_result = rename_keys(result, rename_map)

    return human_readable_result


class Command(BaseCommand):

    def handle(self, *args, **options):

        get_mongo_connection() # connect safely after fork

        pairs = set(
            (
                str(r).strip().upper(),
                str(d).strip().upper()
            )
            for r, d in zip(
                mongo_pages["record_ipno"],
                mongo_pages["document_type"]
            )
        )

        pages = (
            PageImage.objects
            .select_related("pdf__patient", "pdf__document_type", "pdf__patient__hospital")
            .filter(
                pdf__patient__record_ipno__in=[p[0] for p in pairs],
                pdf__document_type__code__in=[p[1] for p in pairs],
            )
        )

        for page in pages:

            record_ipno = str(page.pdf.patient.record_ipno).strip().upper()
            document_type = str(page.pdf.document_type.code).strip().upper()

            # ensure the exact pair exists in the CSV
            if (record_ipno, document_type) not in pairs:
                continue
            
            field_params = page.field_params
          

            if not field_params:
                continue
            
            human_readable_data =  convert_nans(combine_values(field_params, document_type))

            
            try:
                custom_id = f"{document_type}_{record_ipno}_page_{page.page_number}.png"

                doc = PaperRecordPageCollection.objects(id=custom_id).first()

                update_fields = {}

                # Always update timestamps and fixed fields
                update_fields["set__hospital"] = f"{page.pdf.patient.hospital.id}"
                update_fields["set__record_type"] = document_type

                for k, v in human_readable_data.items():
                    field_name = f"{k}"
                    current_value = getattr(doc, field_name, None) if doc else None

                    # CASE 1: Document doesn't exist → allow any value (even None)
                    if not doc:
                        update_fields[f"set__{field_name}"] = v
                        continue

                    # CASE 2: Field missing in doc → allow setting even if None
                    if not hasattr(doc, field_name):
                        update_fields[f"set__{field_name}"] = v
                        continue

                    # CASE 3: Field exists → only update if v is not None and different
                    if v is not None and current_value != v:
                        update_fields[f"set__{field_name}"] = v

                # Only run modify if there’s something to change
                if update_fields:
                    doc = PaperRecordPageCollection.objects(id=custom_id).modify(
                        upsert=True,
                        new=True,
                        **update_fields
                    )
                else:
                    # No changes needed — fetch current doc if not loaded
                    doc = doc or PaperRecordPageCollection.objects(id=custom_id).first()

            except Exception as e:

                logging.error(f"[Task MongoDB] Failed to save record: {e}")
                raise Exception(f"[Task MongoDB] Error: {str(e)}")

        self.stdout.write(self.style.SUCCESS("Mongo insert completed"))

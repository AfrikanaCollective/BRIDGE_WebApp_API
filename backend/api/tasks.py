import os
import io
import re
import cv2
import json
import base64

import numpy as np
from PIL import Image, ImageDraw
import pypdfium2 as pdfium

from collections import defaultdict

import traceback
import logging, logging.config

from celery.exceptions import Ignore
from celery import shared_task, states

import tensorflow as tf
from django.conf import settings
from django.core.files import File

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from .models import PatientDocument, PageImage, Hospital

from .storage_backends import RawImageStorage, ProcessedImageStorage, AlignedImageStorage

from .utils import (
    get_image_contours, 
    get_fiducials, 
    get_pil_image, 
    get_extreme_points,
    get_template_akaze_score,
    align_image_to_template
)

from .model_loader import get_omr_model, get_ocr_model   # import the globals
from .mongo_artefacts import get_mongo_connection, PaperRecordCollection

from .exceptions import SemanticTaskError

logging.config.dictConfig(settings.LOGGING)


aspect_ratio = {
    '1': (0.9,1.1),
    '2': (0.8, 1.2),
    '3': (0.725,1.35),
    '4': (0.65, 1.35),
}

fiducial_size = {
    '1': (1200, 4400),
    '2': (1500, 4400),
    '3': (1800, 4400),
    '4': (2200, 4400),
}

grayscale_percent = {
    '1': 45.0,
    '2': 55.0,
    '3': 65.0
}

filter_mode = {    
    '1': (False, False),
    '2': (True, False),
    '3': (False, True),
    '4': (True, True)    
}

default_params = {        
        "aspect_use":'3',
        "fiducial_use":'4',
        "filter_use":'1',        
        "gray_use":'2',
        "threshold_use": '4'
}

threshold_image = {    
    '1': 71,
    '2': 79,
    '3': 95,
    '4': 127,
    '5': 155,
    '6': 183
}

OCR_CLASS_NAMES = ['$'] + list(range(10)) + ['?'] + ['@'] 

# Define custom combination rules for specific variables
combine_rules = {
    #"parity": lambda vals: f"{vals[0]}+{vals[-1]}" if len(vals) > 1 else "".join(vals),
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

@shared_task
def split_pdf_to_images(pdf_id, user_params):

    print(f"[Task] Starting split for PDF ID {pdf_id}")

    pdf = PatientDocument.objects.get(id=pdf_id)

    try:
        # ✅ Open file from MinIO storage
        with pdf.file.open("rb") as f:
            pdf_bytes = f.read()
        pdf_doc = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
    except Exception as e:
        logging.error(f"[Task ERROR] Could not open PDF ID {pdf_id} from MinIO: {e}")
        return

    n_pages = len(pdf_doc)    
    logging.info(f"[Task] PDF ID {pdf_id} pages from MinIO: {n_pages}")
    
    raw_pdf_page_image_storage = RawImageStorage()

    page_indices = [i for i in range(n_pages)]  # all pages
    renderer = pdf_doc.render(pdfium.PdfBitmap.to_pil,
                            page_indices=page_indices,
                            scale= 300/72 # 300 dpi
    )

    for i, pdf_page in zip(page_indices, renderer): 
            filename = f'{pdf.form_id}_page_{i+1}.png'

            buffer = io.BytesIO()
            pdf_page.save(buffer, format="PNG", dpi=(300, 300))
            buffer.seek(0)            
            content_file = File(buffer, name = filename) # 👈 critical for MinIO backend
            content_file.content_type = "image/png"   # 👈 critical for MinIO headers
            
            try:
                # Save to MinIO
                path_in_bucket = raw_pdf_page_image_storage.save(
                    f"raw_pdf_page_images/{filename}",  # 👈 include subfolder here
                    content_file
                )
                logging.info(f"[Task] Uploaded page {i+1} as {path_in_bucket}")

                # Create DB record
                PageImage.objects.update_or_create(
                    pdf=pdf,
                    page_number = i+1,
                    defaults={                        
                        "image": path_in_bucket,  # ✅ Django will map to MinIO URL
                        "processing_params": user_params  # Values per page
                    }                   
                )

            except Exception as e:
                logging.error(f"[ERROR] Failed to save image for page {i + 1}: {e}")
                continue

            
            try:
                print(f"[Task] Created PageImage for page {i + 1}")
            except Exception as e:
                print(f"[ERROR] Failed to create PageImage for page {i + 1}: {e}")

    pdf.total_pages = n_pages
    pdf.status = "processing"
    pdf.save()

    process_images_sequentially.delay(pdf_id)
    logging.info(f"[Task] Triggered PDF process_images_sequentially")


@shared_task
def process_images_sequentially(pdf_id):
    """
    Processes each image using OpenCV with default parameters.
    Can be extended to support user-specific parameters.
    """
    pages = PageImage.objects.filter(pdf_id=pdf_id).order_by('page_number')

    for page in pages:
        process_single_image.delay(page.id, params=default_params)  # you can pass custom/default params here

    return f"Processed {pages.count()} pages from pdf ID {pdf_id}"


@shared_task(bind=True)
def process_single_image(self, page_id, params):
    """
    Not a task. Called from process_images_sequentially or manually.
    """

    processed_pdf_page_image_storage = ProcessedImageStorage() 

    page = PageImage.objects.get(id=page_id)
    page.status = 'processing'
    page.save()

    form_id = page.pdf.form_id
    filename = f'{form_id}_page_{page.page_number}.png'

    # Load image with OpenCV
    with page.image.open("rb") as f:
        file_bytes = np.asarray(bytearray(f.read()), dtype=np.uint8)
        image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    threshold_use = threshold_image[params["threshold_use"]]
    fiducial_use = fiducial_size[params["fiducial_use"]]
    aspect_use = aspect_ratio[params["aspect_use"]]
    gray_use = grayscale_percent[params["gray_use"]]
    isDilate, isSharpen = filter_mode[params["filter_use"]]
    isFaded = False
    isInverted = False

    if isDilate and isSharpen:
        isFaded = True
        isInverted = True

    image_warp = image.copy()

    bw, contours = get_image_contours(image, threshold_use, isDilate, isSharpen, isFaded)
    fiducials = get_fiducials(contours, bw, gray_use, fiducial_use, aspect_use, isInverted)

    try:
        if (len(fiducials) // 4) > 3: 
            corners = get_extreme_points(fiducials)
            pil_image = get_pil_image(corners, image_warp) 

            # Save into a memory buffer
            buffer = io.BytesIO()
            pil_image.save(buffer, format="PNG", dpi=(300, 300))
            buffer.seek(0)    

            content_file = File(buffer, name = filename) # 👈 critical for MinIO backend
            content_file.content_type = "image/png"   # 👈 critical for MinIO headers

            path_in_bucket = processed_pdf_page_image_storage.save(
                f"processed_pdf_page_images/{filename}",  # 👈 include subfolder here
                content_file
            )

            logging.info(f"[Processing] Processsed page {page_id} image saved to {path_in_bucket}\n")

            page.processed_image = path_in_bucket
            page.processing_params = params
            page.save() 

            

        elif (len(fiducials) // 4) < 4:

            error_msg = "Less than 4 Fiducials identified"
            raise SemanticTaskError(error_msg)
            
        
    except SemanticTaskError as e:  
        self.update_state(
                state=states.FAILURE,
                meta={
                    "error_type": "semantic",
                    "message": e.message
                }
            )
        raise Ignore() 
    
    except Exception as e:
        # Log unexpected errors
        self.update_state(
            state=states.FAILURE,
            meta={"error_type": "exception", "message": str(e)}
        )
        raise Ignore()
    

@shared_task
def get_page_template_score(page_id, template_path): 

    page = PageImage.objects.get(id=page_id)

    # Load image with OpenCV
    # Load image from MinIO
    with page.processed_image.open("rb") as f:
        file_bytes = np.asarray(bytearray(f.read()), dtype=np.uint8)
        page_image = cv2.imdecode(file_bytes, cv2.IMREAD_GRAYSCALE)   
        
    match_score = get_template_akaze_score(page_image, template_path)

    return page_id, template_path, match_score


@shared_task
def aggregate_template_scores(results):
    """
    results = [(page_id, template_path, match_score), ...]
    """
    best_by_page = {}

    for page_id, template_path, score in results:
        if page_id not in best_by_page or score > best_by_page[page_id][1]:
            best_by_page[page_id] = (template_path, score)

    return best_by_page  


@shared_task
def align_page_to_template(page_id, template_path):

    aligned_pdf_page_image_storage = AlignedImageStorage()

    page = PageImage.objects.get(id=page_id)    

    # Load image with OpenCV
    with page.processed_image.open("rb") as f:
        file_bytes = np.asarray(bytearray(f.read()), dtype=np.uint8)
        image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)     

    filename = str(page.processed_image.name.split("/")[-1])

    aligned_image, width, height = align_image_to_template(
        image,
        template_path,
        method_use = "AKAZE" #ORB
    )

    template_field_map = template_path.replace(".png", ".json")
    field_map_data = None

    if os.path.exists(template_field_map):
        with open(template_field_map, 'r') as file:
            field_map_data = json.load(file)
            page.field_params = field_map_data
    else:
        logging.error(f"[Task] Matched align page template:{template_path}, has no corresponding json")  

    masking_field_map = template_field_map.replace("/media/templates/", "/media/masks/")

    mask_map_data = None

    if os.path.exists(masking_field_map):

        draw = ImageDraw.Draw(aligned_image)
        with open(masking_field_map, 'r') as file:
            mask_map_data = json.load(file)
            page.masking_params = mask_map_data

            for item in mask_map_data:
                xmin = item['xmin'] - 1
                ymin = item['ymin'] - 1
                xmax = item['xmax']
                ymax = item['ymax']

                # Draw filled black rectangle (like rgba(0,0,0,1))
                draw.rectangle([xmin, ymin, xmax, ymax], fill=(0, 0, 0))

    else:
        logging.error(f"[Task] Matched align page template:{template_path}, has no corresponding masking json")

    
    # Save into a memory buffer
    buffer = io.BytesIO()
    aligned_image.save(buffer, format="PNG", dpi=(300, 300))
    buffer.seek(0)    

    content_file = File(buffer, name = filename) # 👈 critical for MinIO backend
    content_file.content_type = "image/png"   # 👈 critical for MinIO headers

    path_in_bucket = aligned_pdf_page_image_storage.save(
        f"registered_pdf_page_images/{filename}",  # 👈 include subfolder here
        content_file
    )

    page.aligned_image = path_in_bucket
    page.width = width
    page.height = height
    page.save() 

@shared_task
def predict_field_task(item, roi_bytes, page_id):

    # Convert roi_bytes back to PIL
    roi_image = Image.open(io.BytesIO(roi_bytes)).convert("RGB")

    field_type = item['roi_type']
    img_width, img_height = roi_image.size

    try:
        infer_omr_fn = get_omr_model()
        infer_ocr_fn = get_ocr_model()

        image_tensor = tf.convert_to_tensor(
            np.array(roi_image).reshape(1, img_width, img_height, 3),
            dtype=tf.float32
        )

        if field_type == "character":
            result = infer_ocr_fn(image_tensor)  #infer_ocr_fn(image_tensor)
            predicted_class = OCR_CLASS_NAMES[np.argmax(list(result.values())[0])]
            item['value'] = predicted_class
        else:
            result = infer_omr_fn(image_tensor)  #infer_omr_fn(image_tensor)
            predictions = list(result.values())[0]
            item['value'] = int(np.rint(predictions))

        item['generator'] = 'model'

        return (page_id, item)

    except Exception as e:
        logging.error(f"[Task Error] predict_field_task failed: {e}")
        raise Exception(f"Prediction error from predict_field_task: {str(e)}") 

@shared_task
def aggregate_results(results):
    """
    results = [(page_id, item), (page_id, item), ...]
    """
    from collections import defaultdict
    grouped = defaultdict(list)

    for page_id, item in results:
        grouped[page_id].append(item)

    # Now dispatch save_field_results per page
    for page_id, items in grouped.items():
        save_field_results.delay(items, page_id)

    

@shared_task
def save_field_results(results, page_id):
    try:
        page = PageImage.objects.get(id=page_id)
        page.field_params = results
        page.save(update_fields=['field_params'])
        logging.info(f"[Task] Finished saving ROI slices for page: {page_id}")
    except Exception as e:
        logging.error(f"[Task Error] Failed saving results: {e}")
        raise Exception(f"Prediction error from save_field_results: {str(e)}")
    
@shared_task
def save_page_data(page_id, form_data):

    page = PageImage.objects.get(id=page_id)
    orig_data = page.field_params

    form_type = str(page.pdf.document_type.code)

    verified_data, analysable_data = update_generator_if_value_diff(orig_data, form_data, form=form_type)

    page.field_params = verified_data
    page.status = 'completed'
    page.save()

    return convert_nans(analysable_data)
    
   
def update_generator_if_value_diff(modeled_vals, evaluated_vals, key='id', generator_value='user', form="ITF"):
        
    evaluated_set = {item[key]: item for item in evaluated_vals}
    
    for item in modeled_vals:
        item_id = item[key]

        if item_id in evaluated_set:
            if item.get('value') != evaluated_set[item_id].get('value'):
                # Update generator and value in original set
                item['generator'] = generator_value
                item['value'] = evaluated_set[item_id].get('value')

    combined_data = combine_values(modeled_vals, form)
             
    return modeled_vals, combined_data


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
            values = [str(i['value']) for i in sorted_items]

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

                ones = [i for i in items if i['value'] == 1]
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

    #logging.info("[Task] NAR page 2: {}".format(str(result)))        

    human_readable_result = rename_keys(result, rename_map)

    #if form_type in ["ITF","NAR"]:

    return human_readable_result

@shared_task
def run_prediction_task(base64_image, field_name):
    try:
        #os.environ["CUDA_VISIBLE_DEVICES"] = "-1" # Force CPU use

        image_data = base64.b64decode(base64_image.split(',')[1])
        img = Image.open(io.BytesIO(image_data)).convert('RGB')
        img = img.resize((48, 48))
        
        image_tensor = tf.convert_to_tensor(
            np.array(img).reshape(1, 48, 48, 3), 
            dtype=tf.float32
        )

        infer_fn = get_omr_model()

        result = infer_fn(image_tensor)
        predictions = list(result.values())[0]
        predicted_isSelected = int(np.rint(predictions))

        logging.info("[Task] image field: {}, prediction:{}, class:{}".format(
            str(field_name),
            str(predictions),
            str(predicted_isSelected)
         ))        

        return predicted_isSelected

    except Exception as e:
        traceback_str = traceback.format_exc()
        logging.error(f"[Task ERROR] Prediction task failed: {traceback_str}")
        raise Exception(f"Prediction Error: {str(e)}")
    

@shared_task
def save_to_mongo_db(data_as_dict, pdf_id, hospital_id):

    get_mongo_connection() # connect safely after fork

    pdf_doc = PatientDocument.objects.get(id=pdf_id)
    hospital_name = Hospital.objects.get(id=hospital_id).name
    doc_type = str(pdf_doc.document_type.code).lower()

    nairobi_timezone = ZoneInfo("Africa/Nairobi")

    try:
        # Save the dict
        custom_id = f"{hospital_id}_{pdf_doc.patient.record_ipno}"

        # Fetch the existing document (if any)
        doc = PaperRecordCollection.objects(id=custom_id).first()

        update_fields = {}

        # Always update timestamps and fixed fields
        update_fields["set__hospital"] = hospital_name
        update_fields["set__updated_at"] = datetime.now(nairobi_timezone)
        update_fields["set__admission_date_manual"] = pdf_doc.patient.admission_date
        update_fields["set__discharge_date_manual"] = pdf_doc.patient.discharge_date

        for k, v in data_as_dict.items():
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
            doc = PaperRecordCollection.objects(id=custom_id).modify(
                upsert=True,
                new=True,
                **update_fields
            )
        else:
            # No changes needed — fetch current doc if not loaded
            doc = doc or PaperRecordCollection.objects(id=custom_id).first()

        '''
        doc = PaperRecordCollection.objects(id=custom_id).modify(
            upsert=True,
            new=True, # return the new/updated doc
            set__hospital=hospital_name,
            set__admission_date_manual=pdf_doc.patient.admission_date,
            set__discharge_date_manual=pdf_doc.patient.discharge_date,
	    set__updated_at=datetime.now(nairobi_timezone),
            **{f"set__{doc_type}_{k}": v for k, v in data_as_dict.items()}            
        )
        '''
        #doc.save()

        pdf_doc.status = "completed"
        pdf_doc.save()

        logging.info(f"[Task MongoDB] Modified patient encounter with ID: {doc.id}")

    except Exception as e:
        logging.error(f"[Task MongoDB] Failed to save record: {e}")
        raise Exception(f"[Task MongoDB] Error: {str(e)}")
    

def convert_nans(obj):
    if isinstance(obj, dict):
        return {k: convert_nans(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_nans(x) for x in obj]
    elif isinstance(obj, float) and np.isnan(obj):
        return None
    else:
        return obj

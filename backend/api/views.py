from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from google.oauth2 import id_token
from google.auth.transport import requests

from .models import Hospital, UserType, PatientEncounter, PatientDocument, PageImage, CustomUser, DocumentType, DocumentTransaction, TransactionTaskMap
from .serializers import PageImageSerializer, HospitalSerializer, UserTypeSerializer, PatientEncounterSerializer, CustomUserSerializer, DocumentTypeSerializer

from django.conf import settings
from django.http import JsonResponse
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.contrib.auth import login, logout
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from celery import states, group, chord
from celery.result import AsyncResult, GroupResult
from bridge.celery import app 

from .tasks import split_pdf_to_images
from .tasks import process_single_image
from .tasks import align_page_to_template
from .tasks import run_prediction_task
from .tasks import save_page_data
from .tasks import combine_values
from .tasks import convert_nans
from .tasks import save_to_mongo_db
from .tasks import get_page_template_score
from .tasks import aggregate_template_scores
from .tasks import predict_field_task
from .tasks import aggregate_results

import os
import io
import cv2
import json
import glob
import copy
import numpy as np
from PIL import Image
from dateutil import parser
import logging, logging.config




logging.config.dictConfig(settings.LOGGING)

# Allowed types and size (in bytes)
ALLOWED_TYPES = ['application/pdf']
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024  # 10MB


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
    '1': 0.45,
    '2': 0.55,
    '3': 0.65
}

filter_mode = {    
    '1': (False, False),
    '2': (False, True),
    '3': (True, False),
    '4': (True, True)   
}

threshold_use = {    
    '1': 71,
    '2': 79,
    '3': 95,
    '4': 127,
    '5': 155,
    '6': 183
}

default_params = {
        "gray_use":'2',
        "filter_use":'1',
        "aspect_use":'3',
        "fiducial_use":'4',
        "threshold_use": '4'
    }

'''
Backend Endpoints (Summary):

1. POST /api/upload-pdf/ → upload PDF
2. GET /api/uploads/<pdf_id>/pages/ → get all page info
3. POST /api/pages/<page_id>/update-params/ → save parameters
4. POST /api/pages/<page_id>/reprocess/ → trigger reprocessing

'''

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def revoke_task(request, task_id):
    """
    Revoke a Celery task by task_id.
    Optionally terminate the worker process running it.
    """
    
    try:
        
        task_map = TransactionTaskMap.objects.get(task_id=task_id)

    except TransactionTaskMap.DoesNotExist:
        return Response(
            {"error": "Task not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        # Revoke the task (terminate=True sends SIGTERM to worker)
        task_map.revoke_task(terminate=True, signal="SIGTERM")

        return Response(
            {"message": f"Task {task_id} revoked successfully."},
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_transaction(request, patient_id, document_code):

    try:
        patient = PatientEncounter.objects.get(id=patient_id)
    except PatientEncounter.DoesNotExist:
        return JsonResponse({"error": "Patient not found"}, status=404)

    document_type = DocumentType.objects.filter(code=document_code).first()
    if not document_type:
        return JsonResponse({"error": "Document type not found"}, status=404)
    
    txn = (
        DocumentTransaction.objects
        .filter(patient=patient, document_type=document_type)
        #.exclude(status="committed")   # don't resume committed ones
        .exclude(status="rolled_back") # don't resume rolled back ones
        .order_by("-updated_at")       # latest one
        .first()
    )

    if txn:
        # ✅ Resume transaction
        return JsonResponse({
            "transaction_id": str(txn.id),
            "status": txn.status,
            "current_step": txn.current_step,  # 👈 add this field in your model
            "resumed": True,
        })

    else:
        # 🚀 Create new transaction
        txn = DocumentTransaction.objects.create(
            patient=patient,
            document_type=document_type,
            status="in_progress",
            current_step=0,   # 👈 track wizard step
        )
        return JsonResponse({
            "transaction_id": str(txn.id),
            "status": txn.status,
            "current_step": txn.current_step,
            "resumed": False,
        })

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def commit_transaction(request, txn_id):
    txn = DocumentTransaction.objects.get(id=txn_id)
    txn.status = "committed"
    txn.save()
    return JsonResponse({"status": txn.status})

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def rollback_transaction(request, txn_id):
    txn = DocumentTransaction.objects.get(id=txn_id)
    # cleanup (delete staged files, db rows, etc.)
    # txn.status = "invalid"
    txn.save()
    return JsonResponse({"status": txn.status})

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_step(request, txn_id):
    txn = DocumentTransaction.objects.get(id=txn_id)
    
    # frontend sends the current step index
    step = int(request.data.get("step", txn.current_step))
    txn.status == "in_progress"
    txn.current_step = step
    txn.save()

    return JsonResponse({"message": "Step saved.", "step": step})


@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def transaction_details(request, txn_id):
    txn = DocumentTransaction.objects.get(id=txn_id)

    pdf_id = None

    try:
        # if steps are after upload (i.e. step > 0):
        latest_doc = PatientDocument.objects.filter(
            patient_id=txn.patient.id, 
            document_type_id=txn.document_type.id
        ).latest("uploaded_at")

        pdf_id = latest_doc.id

    except PatientDocument.DoesNotExist:
        logging.info("[View] transaction_details: PatientDocument not found")


    return JsonResponse({
        "status": txn.status,
        "hospital": txn.patient.hospital.name,
        "record": txn.patient.record_ipno,
        "document": txn.document_type.description,
        "pdf_id": pdf_id
    })


@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def document_inference_time(request, pdf_id):

    inference_time = request.data.get('inference_time')
    try:
        doc = PatientDocument.objects.get(id=pdf_id)   
        doc.inference_time = inference_time   
        doc.save() 

    except PatientDocument.DoesNotExist:
        logging.info("[View] document_inference_time: PatientDocument not found")


    return JsonResponse({
        "message": "Inference time for saved",
        "pdf_id": pdf_id
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_task_status(request, task_id):
    result = AsyncResult(task_id)

    response_data = {
        "task_id": task_id,
        "status": result.status,
    }

    if result.state == states.SUCCESS:        
        returned_value = result.result

        if returned_value is not None:
            response_data["savedData"] = returned_value
            response_data["message"] = returned_value

        return JsonResponse(response_data)
    

    elif result.status == states.FAILURE:
        error_info = result.result if isinstance(result.result, dict) else {"message": str(result.result)}
        response_data["error"] = error_info["message"]

        return JsonResponse(response_data)
    
    elif result.state in [states.PENDING, states.RECEIVED, states.STARTED, states.RETRY]:
        return JsonResponse({
            "task_id": task_id,
            "status": result.state,
            "message": f"Task {task_id} is in progress..."
        })

    else:
        return JsonResponse({
            "status": result.state,
            "message": "Unexpected task state."
        }, status=500)
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def template_match_task_status(request, task_id):
    result = AsyncResult(task_id)

    # Always return current state
    response_data = {
        "status": result.status,
    }

    if result.state == states.SUCCESS:

        aggregated = result.result

        # Make it JSON-friendly (avoid tuples)
        best_by_page = {
            str(score): {
                "template": template_path,
                "page": page_id
            }
            for page_id, (template_path, score) in aggregated.items()
        }

        response_data["result"] = best_by_page

    elif result.status == states.FAILURE:
        response_data["error"] = str(result.result)


    return Response(response_data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_group_task_status(request, task_id):
    
    group_result = GroupResult.restore(task_id)

    if group_result is None:
        return JsonResponse({
            "status": "unknown",
            "message": "No such group result"
        }, status=404)

    if group_result.ready():
        try:
            results = group_result.get()
            return JsonResponse({
                "task_id": task_id,
                "status": "SUCCESS",
                "results": results
            })
        except Exception as e:
            return JsonResponse({
                "task_id": task_id,
                "status": "FAILURE",
                "error": str(e)
            })

    return JsonResponse({
        "task_id": task_id,
        "status": "PENDING",
        "completed": group_result.completed_count(),
        "total": len(group_result.results),
    })

@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser, JSONParser])
@permission_classes([IsAuthenticated])
def upload_pdf(request):
         
    uploaded_file = request.FILES.get('file')
    transactionId = request.data.get('transactionId')
    clerk_email = request.data.get('userEmail')
    transaction = DocumentTransaction.objects.get(id=transactionId)   
    
    dataClerk = CustomUser.objects.filter(username=clerk_email).first()

    if not dataClerk:
        dataClerk = CustomUser.objects.filter(email=clerk_email).first()


    form_id = transaction.document_type.code + "_" + transaction.patient.record_ipno

    if not uploaded_file:
        return Response({'error': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

    if uploaded_file.content_type not in ALLOWED_TYPES:
        return Response({'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_TYPES)}'},
                        status=status.HTTP_400_BAD_REQUEST)

    if uploaded_file.size > MAX_FILE_SIZE:
        return Response({'error': f'File too large. Max size is {MAX_FILE_SIZE_MB}MB.'},
                        status=status.HTTP_400_BAD_REQUEST)
    
    processing_params = request.data.get('params', default_params)

    pdf, created = PatientDocument.objects.update_or_create(
        form_id=form_id,
        defaults={
            "file": uploaded_file,
            "patient": transaction.patient,
            "document_type" : transaction.document_type,
            "uploaded_by" : dataClerk,
            "status": "uploaded"
        }
    )  

    # Save values or pass them to the background task
    task = split_pdf_to_images.delay(pdf.id, processing_params)

    return Response({'pdf_id': pdf.id, 
                     "pages": pdf.pages.count(),
                     "task_id": task.id,
                     "created": created
                     }, status=202)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_pdf_status(request, pdf_id):
    try:
        pdf = PatientDocument.objects.get(id=pdf_id)
        return Response({'status': pdf.status})
    except PatientDocument.DoesNotExist:
        return Response({'error': 'PDF not found'}, status=404)
    

@api_view(['POST'])
@parser_classes([JSONParser])
@permission_classes([IsAuthenticated])
def get_page_list(request):

    pdf_id = request.data['pdf_id']

    pages = PageImage.objects.filter(pdf_id=pdf_id).order_by('page_number')
    serializer = PageImageSerializer(pages, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_processing_params(request):
    
    
    user_params = request.data['user_params']
    page_id = request.data['page_id']

    if not user_params:
        user_params = default_params

    page = PageImage.objects.get(id=page_id)
    page.processing_params = user_params
    page.status = 'pending'
    page.save()

    serializer = PageImageSerializer(page,context={'request': request})
    
    return Response({"message": "Params updated", 
                     "updatedPage": serializer.data}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reprocess_page(request):
    
    page_id = request.data['page_id']
    processing_params = request.data.get("user_params", default_params)

    task = process_single_image.delay(page_id, processing_params)


    page = PageImage.objects.get(id=page_id)
    serializer = PageImageSerializer(page,context={'request': request})

    return Response({"task_id": task.id,  
                     "message": "Image reprocess initiated",
                     "updatedPage": serializer.data} ,status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def find_optimum_templates(request):

    pdf_id = request.data['pdf_id']
    hospital_name = request.data['hospital_name']
    transactionId = request.data['transaction_id']

    pdf_doc = PatientDocument.objects.get(id = pdf_id)
    doc_type = pdf_doc.document_type.code

    pages = pdf_doc.pages.all()

    template_dir = os.path.join(settings.MEDIA_ROOT, settings.TEMPLATE_DIR_NAME)  

    all_tasks = []

    for page in pages:       

        hospital_specific_template_path_list = glob.glob(
            os.path.join(
                template_dir, 
                hospital_name, 
                "**", 
                f"{doc_type}_page_{page.page_number}.png"),
            recursive=True) 
        
        other_template_path_list = glob.glob(
            os.path.join(
                template_dir, 
                "Other", 
                "**", 
                f"{doc_type}_page_{page.page_number}.png"),
            recursive=True) 
        
        template_path_list = hospital_specific_template_path_list + other_template_path_list

        for template_path in template_path_list:
            all_tasks.append(
                get_page_template_score.s(page.id, template_path)
            )


    chord_result = chord(all_tasks)(aggregate_template_scores.s())

    TransactionTaskMap.objects.create(
        transaction_id=transactionId,
        task_id=chord_result.id,
        task_type="template",
        #user=request.user,
    )

    return Response({"task_id": chord_result.id,  
                    "message": "Page template search initiated"} ,status=status.HTTP_200_OK)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def align_pages_to_template(request):

    transactionId = request.data['transaction_id']
    
    template_info = list(request.data['matches'].values())   

    all_tasks = []
    for image_template_pair in template_info:

        page_id, template_path =  image_template_pair['page'], image_template_pair['template']

        all_tasks.append(
            align_page_to_template.s(page_id, template_path)
        )

    task_group = group(all_tasks)
    group_task_result = task_group.apply_async()
    GroupResult(group_task_result.id, group_task_result.results).save()

    TransactionTaskMap.objects.create(
        transaction_id=transactionId,
        task_id= group_task_result.id,
        task_type="align",
        #user=request.user,
    )

    return Response({"task_id": group_task_result.id,  
                    "message": "Page alignment processing initiated"} ,status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_extract_page_data(request):
    
    pdf_id = request.data['pdf_id']  
    transactionId = request.data['transaction_id']
    pages = PageImage.objects.filter(pdf_id=pdf_id).order_by('page_number')

    all_tasks = []

    for page in pages:

        # Load image with OpenCV
        with page.aligned_image.open("rb") as f:
            file_bytes = np.asarray(bytearray(f.read()), dtype=np.uint8)
            image = cv2.imdecode(file_bytes, cv2.IMREAD_GRAYSCALE) 

        field_map = copy.deepcopy(page.field_params)

        for item in field_map:

            field_type = item['roi_type']
            xmin, ymin, xmax, ymax = item['xmin'], item['ymin'], item['xmax'], item['ymax']
            img_width, img_height = (64, 64) if field_type == "character" else (48, 48)

            # Crop the ROI from the page image
            roi = image[ymin:ymax, xmin:xmax]
            pil_image = Image.fromarray(roi).convert("RGB").resize((img_width, img_height))

            buffer = io.BytesIO()
            pil_image.save(buffer, format="PNG")
            roi_bytes = buffer.getvalue() # JSON serialisable Image Object for Celery task

            all_tasks.append(
                predict_field_task.s(item, roi_bytes, page.id) 
            )

    chord_result = chord(all_tasks)(aggregate_results.s())

    TransactionTaskMap.objects.create(
        transaction_id=transactionId,
        task_id= chord_result.id,
        task_type="extract",
        #user=request.user,
    )

    return Response({"task_id": chord_result.id,  
                    "message": "PDF upload data extraction initiated"} ,status=status.HTTP_200_OK)

        

@api_view(['POST'])
@parser_classes([JSONParser])
@permission_classes([IsAuthenticated])
def canvas_images(request):

    pdf_id = request.data['pdf_id']

    pages = PageImage.objects.filter(pdf_id=pdf_id).order_by('page_number')
    serializer = PageImageSerializer(pages, many=True, context={'request': request})
    return Response(serializer.data)

@api_view(['POST'])
@parser_classes([JSONParser])
@permission_classes([IsAuthenticated])
def predict_from_canvas(request):   
    data = json.loads(request.body)
    base64_image = data.get('image')
    field_name = data.get('field')


    task = run_prediction_task.delay(base64_image, field_name)

    return JsonResponse({"task_id": task.id})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_prediction_result(request, task_id):
    result = AsyncResult(task_id)

    response_data = {
        "task_id": task_id,
        "status": result.state
    }

    if result.state == states.SUCCESS:
        response_data["prediction"] = str(result.result)
        return JsonResponse(response_data)    

    elif result.status == states.FAILURE:
        logging.info('Prediction Task Failed [View]: {}'.format(result.result))
        response_data["error"] = str(result.result)

        return JsonResponse(response_data)
    
    elif result.state in [states.PENDING, states.RECEIVED, states.STARTED, states.RETRY]:
        response_data["message"] = "Prediction task is in progress..."           

    else:
        response_data["message"] = "Unexpected task state."

    return JsonResponse(response_data)


@api_view(['POST'])
@parser_classes([JSONParser])
@permission_classes([IsAuthenticated])
def save_page_edit(request):
         
    page_id = request.data['page_id']
    page_data = request.data['field_data']
    
    task = save_page_data.delay(page_id, page_data)

    return Response({
        'task_id': task.id, 
        "message": "Page data saving started"}, 
        status=202)



@api_view(["POST"])
@parser_classes([JSONParser])
@permission_classes([IsAuthenticated])
def get_processed_form_data(request):
    
    pdf_id = request.data['pdf_id']

    pdf_doc = PatientDocument.objects.get(id = pdf_id)
    pdf_pages = pdf_doc.pages.all()

    pdf_data = []

    for page in pdf_pages:
        page_data = page.field_params
        pdf_data = pdf_data + page_data

    human_readable_data = convert_nans(combine_values(pdf_data, pdf_doc.document_type.code))
   
    return Response({
        'form_data': human_readable_data, 
        "message": "Page data extracted"}, 
        status=202)


@api_view(["POST"])
@parser_classes([JSONParser])
@permission_classes([IsAuthenticated])
def save_processed_form_data(request):
    
    pdf_id = request.data['pdf_id']
    human_readable_data = request.data['human_readable_data']

    pdf_doc = PatientDocument.objects.get(id = pdf_id)

    task = save_to_mongo_db.delay(
        human_readable_data,
        pdf_id,
        pdf_doc.patient.hospital.id
    )

    return Response({
        'form_data': human_readable_data, 
        'task_id': task.id,
        "message": "Page data saving started"}, 
        status=202)


@api_view(['GET'])
def get_jwt_token(request):
    if not request.user.is_authenticated:
        return Response({"error": "Please sign in first"}, status=401)
    refresh = RefreshToken.for_user(request.user)
    return Response({
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    })

@csrf_exempt
@api_view(["POST"])
def exchange_google_token(request):
    """
    Called after Google login on frontend.
    Expects: { "access_token": "<google_id_token>" }
    """
    token = request.data.get("access_token")
    if not token:
        return Response({"error": "Missing Google token"}, status=400)

    try:
        # Validate token with Google
        idinfo = id_token.verify_oauth2_token(token, requests.Request())
        
        email = idinfo["email"]
        first_name = idinfo.get("given_name", "")
        last_name = idinfo.get("family_name", "")

        # Get or create user
                
        user, created = CustomUser.objects.get_or_create(
            email=email, 
            defaults={
                "username": email,
                "first_name": first_name,
                "last_name": last_name,
            })
        
        # set backend manually
        user.backend = "api.backends.ApprovedUserBackend"
        
        # If not created, update first/last name from Google
        if not created:
            changed = False
            if not user.first_name or user.first_name != first_name:
                user.first_name = first_name
                changed = True
            if not user.last_name or user.last_name != last_name:
                changed = True
            if changed:                
                user.save()


         # Start Django session
        login(request, user)
        request.session["google_email"] = email
        request.session["login_method"] = "google"


        # Issue JWT
        refresh = RefreshToken.for_user(user)

         # Case 1: User must provide more details
        if not user.profile_completed:

            # Check missing fields
            update_fields = []
            update_fields.append("first_name")
            if not user.last_name:
                update_fields.append("last_name")
            if not user.hospital:
                update_fields.append("hospital")
            if not user.hospital:
                update_fields.append("hospital")
            if not user.password:
                update_fields.append("password")
            if not user.phone:
                update_fields.append("phone")

            return Response({
                "status": "incomplete_profile",
                "message": "Additional details required",
                "session_id": request.session.session_key,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": {
                    "email": user.email, 
                    "first_name": user.first_name},
                "update_fields": update_fields
            }, status=200)

        
        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "session_id": request.session.session_key,
            "user": {"email": user.email, "full_name": user.full_name}
        })
    except Exception as e:
        return Response({"error": str(e)}, status=400)
    

@api_view(["POST"])
def logout_view(request):
    logout(request)  # clears Django session
    return Response({"message": "Logged out"})


@api_view(["GET"])
@parser_classes([JSONParser])
@permission_classes([IsAuthenticated])   # or IsAuthenticated, depending on use
def patient_list(request):
    """
    Returns all patient encounters for DocumentAI.js
    """
    encounters = PatientEncounter.objects.filter(is_archived=False).order_by("-date_created")
    serializer = PatientEncounterSerializer(encounters, many=True)
    return Response(serializer.data)


@csrf_exempt
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_encounters(request):

    record_ipno = request.query_params.get("ipno")
    hospital_id = request.query_params.get("hospital")
    
    try:
        encounters = PatientEncounter.objects.filter(is_archived=False)

        if hospital_id:
            encounters = encounters.filter(hospital_id=hospital_id)

        if record_ipno:
            encounters = encounters.filter(record_ipno__icontains=record_ipno)

        encounters = encounters.order_by("-date_created")

    except PatientEncounter.DoesNotExist:
        return JsonResponse({"error": "Patient not found"}, status=404)
    
    serializer = PatientEncounterSerializer(encounters, many=True)
    return Response(serializer.data)

    

@api_view(["POST"])
@parser_classes([JSONParser])
@permission_classes([IsAuthenticated])   # or IsAuthenticated, depending on use
def archive_patient(request):
    """
    Archive patient's encounter from DocumentAI.js
    """
    encounter_id = request.data.get('encounter_id') 
    is_archived = request.data.get('is_archived') 

    encounter = PatientEncounter.objects.get(id=encounter_id)
    encounter.is_archived = is_archived
    encounter.save()

    return Response({"message": f"Archiving encounter {encounter_id} successful"})


@api_view(['POST'])
@parser_classes([FormParser, JSONParser])
@permission_classes([IsAuthenticated])
def add_patient(request):
         
    record_ipno = request.data.get('record_ipno')
    clerk_email = request.data.get('userEmail')

    hospital_id = request.data.get('hospital')
    hospital = Hospital.objects.get(id=hospital_id)

    admissionDate = request.data.get('admission_date')
    dischargeDate = request.data.get('discharge_date')

    admit_dt = parser.parse(admissionDate)
    admit_formatted = admit_dt.strftime("%Y-%m-%d")

    discharge_dt = parser.parse(dischargeDate)
    discharge_formatted = discharge_dt.strftime("%Y-%m-%d")

    dataClerk = CustomUser.objects.filter(username=clerk_email).first()  

    if not dataClerk:
          dataClerk = CustomUser.objects.filter(email=clerk_email).first()  

    patient = PatientEncounter.objects.create(
            record_ipno = record_ipno,
            hospital=hospital,
            admission_date = admit_formatted,
            discharge_date = discharge_formatted,
            created_by = dataClerk,
    )
    

    return Response({'patient_id': patient.id}, status=202)
    

@api_view(["GET"])
@permission_classes([AllowAny])   # or IsAuthenticated, depending on use
def hospital_list(request):
    """
    Returns all available hospitals for dropdown in CompleteProfile.js
    """
    hospitals = Hospital.objects.all().order_by("name")
    serializer = HospitalSerializer(hospitals, many=True)
    return Response(serializer.data)

@api_view(["GET"])
@permission_classes([AllowAny])   # or IsAuthenticated, depending on use
def user_type_list(request):
    """
    Returns all available hospitals for dropdown in CompleteProfile.js
    """
    userTypes = UserType.objects.all().order_by("description")
    serializer = UserTypeSerializer(userTypes, many=True)
    return Response(serializer.data)

@api_view(["GET"])
@permission_classes([AllowAny])   # or IsAuthenticated, depending on use
def record_type_list(request):
    """
    Returns all available hospitals for dropdown in CompleteProfile.js
    """
    docTypes = DocumentType.objects.all().order_by("code")
    serializer = DocumentTypeSerializer(docTypes, many=True)
    return Response(serializer.data)



@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_user_profile(request):
    """
    Update user profile (first_name, last_name, phone_number, hospital).
    """
    user = request.user
    data = request.data

    # Update basic fields if provided
    if "first_name" in data:
        user.first_name = data["first_name"]

    if "last_name" in data:
        user.last_name = data["last_name"]

    if "phone" in data:
        user.phone = data["phone"]

    if data.get("password"):
        password = data.get("password")
        user.set_password(password) 

    if "hospital" in data:
        try:
            hospital = Hospital.objects.get(id=data["hospital"])
            user.hospital = hospital
        except Hospital.DoesNotExist:
            return Response({"error": "Hospital not found"}, status=status.HTTP_400_BAD_REQUEST)
    
    '''
    user_data = request.data.copy()
    user_data.pop("hospital", None)
    user_data.pop("confirm_password", None)

    logging.info(f"user data {user_data.values()}")
        
    all_filled = all(v not in [None, ""] for v in user_data.values())
    '''

    required_fields = ["first_name", "last_name", "phone", "email", "password"]

    all_filled = all(
        getattr(user, field) not in [None, ""]
        for field in required_fields
    )

    if all_filled:
        user.profile_completed = True

    user.save()

    return Response(
        {
            "message": "Profile updated successfully",
            "user": {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": getattr(user, "phone", None),
                "hospital": user.hospital.name if user.hospital else None,
            },
        },
        status=status.HTTP_200_OK,
    )
   

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit_additional_details(request):
    user = request.user
    user.hospital = request.data.get("hospital", "")
    user.phone = request.data.get("phone", "")
    user.profile_completed = True  # completed
    user.save()
    return Response({"message": "Details submitted, waiting for approval."})


@api_view(["POST"])
def approve_user(request, user_id):

    token = request.data.get("token")
    signer = TimestampSigner()
    try:
        unsigned_id = signer.unsign(token, max_age=60*60*24)  # valid for 24h
    except SignatureExpired:
        return Response({"error": "Approval link expired"}, status=status.HTTP_400_BAD_REQUEST)
    except BadSignature:
        return Response({"error": "Invalid approval token"}, status=status.HTTP_400_BAD_REQUEST)

    if str(unsigned_id) != str(user_id):
        return Response({"error": "Token does not match user"}, status=status.HTTP_400_BAD_REQUEST)

    """
    Superuser approves a user and updates hospital/user_type.
    """

    try:
        user = get_object_or_404(CustomUser, id=user_id)

        hospital_id = request.data.get("hospital")
        user_type_id = request.data.get("user_type")

        if not user_type_id:
            return Response(
                {"error": "User Type is required."},
                status=400,
            )
        
        user_type = UserType.objects.get(id=user_type_id)
        user.user_type = user_type
        
        if not hospital_id and user_type.code != "DM":
            return Response(
                {"error": "Hospital is required."},
                status=400,
            )
        
        if hospital_id:
            hospital = Hospital.objects.get(id=hospital_id)
            user.hospital = hospital

        # Update + activate
        user.is_approved = True
        user.is_notified = True
        user.save()

        

        return Response({"message": f"User {user.email} approved successfully."})
    
    except CustomUser.DoesNotExist:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
    

@api_view(["GET"])
def get_user_detail(request, user_id):
    """Return user details for approval form, using signed token instead of login."""

    token = request.GET.get("token")
    if not token:
        return Response({"error": "Missing token"}, status=400)

    signer = TimestampSigner()

    try:
        unsigned = signer.unsign(token, max_age=60*60*24)  # valid for 24h
        if str(unsigned) != str(user_id):
            return Response({"error": "Invalid token-user match"}, status=403)
    except SignatureExpired:
        return Response({"error": "Token expired"}, status=403)
    except BadSignature:
        return Response({"error": "Invalid token"}, status=403)
    except Exception as e:
        return Response({"error": f"Unexpected: {str(e)}"}, status=500)
    
    user = get_object_or_404(CustomUser, id=user_id)

    serializer = CustomUserSerializer(user)

    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_session_info(request):
    # Get the email stored in session
    email = request.session.get("google_email")
    if not email:
        return Response({"error": "No session info found"}, status=401)

    try:
        user = CustomUser.objects.get(email=email)
        # Assuming you have a field like 'user_type' or 'is_approved'
        user_type = user.user_type.code
        is_approved = user.is_approved

        response_data = {
            "email": email,
            "approved": is_approved,
            "user_type": user_type,
        }

        if user.hospital:
            response_data['hospital_id'] = user.hospital.id
            response_data['hospital_name'] = user.hospital.name
       
        
        return Response(response_data)
    except CustomUser.DoesNotExist:
        return Response({"error": "User not found"}, status=404)
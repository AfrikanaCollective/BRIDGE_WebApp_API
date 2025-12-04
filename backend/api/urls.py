from django.urls import path, include
from rest_framework.routers import DefaultRouter

from rest_framework_simplejwt.views import TokenRefreshView
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie

from . import views

from .views import (
    patient_list,
    add_patient,
    upload_pdf,
    get_pdf_status,
    get_page_list,
    update_processing_params,
    reprocess_page,
    check_task_status,
    check_group_task_status,
    template_match_task_status,
    find_optimum_templates,
    align_pages_to_template,
    canvas_images,
    predict_from_canvas,
    get_prediction_result,
    save_page_edit,
    exchange_google_token,
    hospital_list,
    user_type_list,
    record_type_list,
    update_user_profile,
    approve_user,
    get_user_detail,
    logout_view,
    get_session_info,
    get_processed_form_data,
    ai_extract_page_data
)


@ensure_csrf_cookie
def set_csrf(request):
    return JsonResponse({"detail": "CSRF cookie set."})


router = DefaultRouter()



'''

| Route                                  | Purpose                         |
| -------------------------------------- | ------------------------------- |
| `POST /upload-pdf/`                    | Upload PDF and start processing |
| `GET /uploads/<upload_id>/pages/`      | List page images                |
| `POST /pages/<page_id>/update-params/` | Save OpenCV params              |
| `POST /pages/<page_id>/reprocess/`     | Reprocess a single page         |


'''

urlpatterns = [
    path('', include(router.urls)),
    path("csrf/", set_csrf,  name="get_csrf_token"),
    path("transactions/start/<int:patient_id>/<str:document_code>/", views.start_transaction),
    path("transactions/commit/<uuid:txn_id>/", views.commit_transaction),
    path("transactions/rollback/<uuid:txn_id>/", views.rollback_transaction),
    path("transactions/save_step/<uuid:txn_id>/", views.save_step),
    path("transactions/details/<uuid:txn_id>/", views.transaction_details),
    path("tasks/<str:task_id>/revoke/", views.revoke_task, name="revoke-task"),

    path("patients/", patient_list,  name="patient_list"), 
    path("encounters/", views.search_encounters,  name="search_encounter_list"), 
    path("patients/archive/", views.archive_patient,  name="archive_patient"),
    path("patients/add", add_patient,  name="add_patient"),
    path('upload_pdf/', upload_pdf, name="upload_pdf"),
    path('pdf_status/<int:pdf_id>/', get_pdf_status, name="get_pdf_status"),
    path('pages/', get_page_list, name="get_page_list"),
    path('pages/update-params/', update_processing_params, name="update_processing_params"),
    path('pages/reprocess/', reprocess_page, name="reprocess_page"),
    path('pages/template/', find_optimum_templates, name="find_optimum_templates"),
    path('pages/align/', align_pages_to_template, name="align_pages_to_template"),
    path('extract_ai/', ai_extract_page_data, name="ai_extract_page_data"),
    path('pages/save/', save_page_edit, name="save_page_edit"),
    path('task-status/<str:task_id>/', check_task_status, name="check_task_status"),
    path('group-task-status/<str:task_id>/', check_group_task_status, name="check_group_task_status"),
    path('template-match-task-status/<str:task_id>/', template_match_task_status, name="template_match_task_status"),
    path('upload_ai/', canvas_images, name="upload_ai"),
    path('predict/', predict_from_canvas, name="predict_value"),
    path('prediction-status/<str:task_id>/', get_prediction_result, name="check_prediction_status"),
    path("inference-time/<int:pdf_id>/", views.document_inference_time),
    path('form-data/', get_processed_form_data, name="view_form_data"),
    path('save-data/', views.save_processed_form_data, name="save_form_data"),

    path("auth/google/", exchange_google_token, name="google_login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", logout_view, name="logout"),
    path("hospitals/", hospital_list, name="hospital-list"),
    path("user-types/", user_type_list, name="user-type-list"),
    path("record-types/", record_type_list, name="record-type-list"),
    path("user/update/", update_user_profile, name="update_user_profile"),
    path("users/<int:user_id>/", get_user_detail, name="user_detail"),
    path("users/<int:user_id>/approve/", approve_user, name="approve_user"),

    path("get-session-info/", get_session_info, name="get_session_info"),

    



]
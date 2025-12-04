import uuid
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser

from .storage_backends import PdfsStorage, RawImageStorage, ProcessedImageStorage, AlignedImageStorage


class Hospital(models.Model):
    redcap_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=100, unique=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True) 

    def __str__(self):
            return self.name
    

class UserType(models.Model):
    code = models.CharField(max_length=10, unique=True)
    description = models.CharField(
        max_length=255, blank=True, 
        help_text="Description of the document type.",
        verbose_name="Document Description")

    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code + ": " + self.description

class CustomUser(AbstractUser):
    profile_completed = models.BooleanField(default=False)   # needs to add more details
    is_approved = models.BooleanField(default=False)          # admin approval
    is_notified = models.BooleanField(default=False)          # admin approval
    hospital = models.ForeignKey(
        Hospital, 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True,
        related_name="active_users")
    user_type = models.ForeignKey(
        UserType,
        on_delete=models.PROTECT,   # Prevent deleting a doc type if PDFs use it
        null=True, 
        blank=True,
        related_name="user_types",
        help_text="Type of document this PDF belongs to"
    )
    phone = models.CharField(max_length=20, blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return self.username
    

class UserHospitalHistory(models.Model):
    """Keeps track of all organizations a user has been part of."""

    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="hospital_history")
    hospital = models.ForeignKey(
        Hospital, on_delete=models.CASCADE, related_name="user_history")
    joined_at = models.DateTimeField()
    left_at = models.DateTimeField(blank=True, null=True)
    reason = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-joined_at"]

    def __str__(self):
        return f"{self.user.username} in {self.hospital.name} ({self.joined_at.date()} → {self.left_at.date() if self.left_at else 'present'})"

    

def move_to_hospital(self, new_hosptial: Hospital, reason: str = None):
        """Update user’s hospital and log history."""
        # close current history record if exists
        UserHospitalHistory.objects.filter(
            user=self, left_at__isnull=True
        ).update(left_at=timezone.now())

        # create new history record
        UserHospitalHistory.objects.create(
            user=self,
            current_hospital=new_hosptial,
            joined_at=timezone.now(),
            reason=reason,
        )

        # update current organization
        self.current_hospital = new_hosptial
        self.save()
    

class DocumentType(models.Model):
    code = models.CharField(max_length=10, unique=True)
    description = models.CharField(
        max_length=255, blank=True, 
        help_text="Description of the document type.",
        verbose_name="Document Description")

    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code + ": " + self.description
    

class PatientEncounter(models.Model):
    record_ipno = models.CharField(max_length=50, blank=False, unique=True, help_text="Hospital IPNO number")
    admission_date = models.DateField(null=False, blank=False)
    discharge_date = models.DateField(null=False, blank=False)

    hospital = models.ForeignKey(
        Hospital, 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True,
        related_name="patients")
    
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,   # Prevent deleting a user if PDFs linked to them
        related_name="patients"
    )
    
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['-date_updated']  # Change 'redcap_id' to a relevant field

    @property
    def nar_document(self):
        return self.documents.filter(document_type__code='NAR').first()

    @property
    def itf_document(self):
        return self.documents.filter(document_type__code='ITF').first()

    @property
    def dsc_document(self):
        return self.documents.filter(document_type__code='DSC').first()

    def __str__(self):
        return f"Patient {self.record_ipno}"
    

class PatientDocument(models.Model):

    PROCESSING_STATUS = [        
        ("uploaded", "Uploaded"),
        ("processing", "Processing"),
        ("completed", "Completed"),        
    ]

    patient = models.ForeignKey(
        PatientEncounter,
        on_delete=models.PROTECT,   # Prevent deleting a patient if PDFs use it
        related_name="documents"
    )

    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.PROTECT,   # Prevent deleting a doc type if PDFs use it
        related_name="documents",
        help_text="Type of document this PDF belongs to"
    )

    uploaded_by = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,   # Prevent deleting a user if PDFs linked to them
        related_name="documents"
    )

    file = models.FileField(
        storage=PdfsStorage(), 
        upload_to="pdfs/")
    
    status = models.CharField(max_length=20, choices=PROCESSING_STATUS, default="uploaded")

    inference_time = models.IntegerField(default=-1)
    
    form_id = models.CharField(max_length=20, unique=True, default=timezone.now)
    uploaded_at = models.DateTimeField(auto_now_add=True)      
    
    total_pages = models.PositiveIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)

    # For audit or filtering
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    def __str__(self):
        return self.form_id
    


class PageImage(models.Model):
    pdf = models.ForeignKey(PatientDocument, on_delete=models.PROTECT, related_name='pages')
    page_number = models.IntegerField()
    image = models.ImageField(
        storage=RawImageStorage(), 
        upload_to="raw_pdf_page_images/"
    )
    processed_image = models.ImageField(
        storage=ProcessedImageStorage(), 
        upload_to="processed_pdf_page_images/", 
        null=True, blank=True)
    
    aligned_image = models.ImageField(
        storage=AlignedImageStorage(), 
        upload_to="registered_pdf_page_images/", 
        null=True, blank=True)
    
    processing_params = models.JSONField(default=dict, null=True, blank=True)
    width = models.SmallIntegerField(null=True, blank=True)
    height = models.SmallIntegerField(null=True, blank=True)
    field_params = models.JSONField(default=dict, null=True, blank=True)
    masking_params = models.JSONField(default=dict, null=True, blank=True)
    status = models.CharField(max_length=20, default='pending') # pending, processing, completed

    def __str__(self):
        return f"IP/No: {self.pdf.patient.record_ipno} ({self.pdf.document_type.code}): {self.status}"


class DocumentTransaction(models.Model):
    TRANSACTION_STATUS = [
        ("in_progress", "In Progress"),
        ("invalid", "Invalid"),
        ("committed", "Committed"),        
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        PatientEncounter,
        on_delete=models.PROTECT,   # Prevent deleting a patient the transaction references
        related_name="transactions"
    )

    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.PROTECT,   # Prevent deleting a doc type the transaction references
        related_name="transactions"
    )

    current_step = models.IntegerField(default=0)  # Upload=0, Preprocess=1, etc.

    status = models.CharField(max_length=20, choices=TRANSACTION_STATUS, default="in_progress")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"IP/No: {self.patient.record_ipno} ({self.document_type.code}): {self.status}"


class TransactionTaskMap(models.Model):
    """
    Tracks Celery tasks linked to a specific user transaction.
    Used to revoke or monitor running tasks if a transaction is canceled.
    """

    TASK_TYPES = [
        ("template", "Template Detection"),
        ("align", "Alignment"),
        ("extract", "AI Extraction"),
        ("upload", "AI Upload"),
        ("other", "Other"),
    ]

    transaction_id = models.CharField(max_length=100, db_index=True)
    task_id = models.CharField(max_length=255, unique=True)
    task_type = models.CharField(max_length=50, choices=TASK_TYPES, default="other")
    #user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    status = models.CharField(max_length=50, default="PENDING")
    error_message = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Transaction Task Map"
        verbose_name_plural = "Transaction Task Maps"
        indexes = [
            models.Index(fields=["transaction_id", "task_type"]),
        ]

    def __str__(self):
        return f"{self.transaction_id} → {self.task_type} ({self.task_id})"

    # optional helper to easily revoke the task
    def revoke_task(self, terminate=False, signal="SIGTERM"):
        from celery.app.control import Control
        from celery import current_app

        control = Control(app=current_app)
        control.revoke(self.task_id, terminate=terminate, signal=signal)
        self.status = "REVOKED"
        self.save(update_fields=["status"])



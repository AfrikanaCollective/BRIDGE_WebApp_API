from rest_framework import serializers
from .models import PatientDocument, PageImage, Hospital, DocumentType, UserType, CustomUser, PatientEncounter

class HospitalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hospital
        fields = ["id", "redcap_id", "name"]

class UserTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserType
        fields = ["id", "code", "description"]

class DocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentType
        fields = ["id", "code", "description"]


class PatientEncounterSerializer(serializers.ModelSerializer):

    hospital_name = serializers.SerializerMethodField()

    itf_stage = serializers.SerializerMethodField()
    nar_stage = serializers.SerializerMethodField()
    dsc_stage = serializers.SerializerMethodField()


    class Meta:
        model = PatientEncounter
        fields = ["id", "hospital", "record_ipno", "date_created",
                  "admission_date", "discharge_date", "hospital_name", 
                  "itf_stage", "nar_stage", "dsc_stage", "is_archived"]
        
    def get_itf_stage(self, obj):
        itf = obj.itf_document

        if itf:
            if itf.status == "processing":
                return 1
            if itf.status == "completed":
                return 2
        return 0
    
    def get_nar_stage(self, obj):
        nar = obj.nar_document

        if nar:
            if nar.status == "processing":
                return 1
            if nar.status == "completed":
                return 2
        return 0
    
    def get_dsc_stage(self, obj):
        dsc = obj.dsc_document

        if dsc:
            if dsc.status == "processing":
                return 1
            if dsc.status == "completed":
                return 2
        return 0
   
    def get_hospital_name(self, obj):
        hospital = obj.hospital
        if hospital:
            return hospital.name
        
        return None
    


class PageImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    processed_image = serializers.SerializerMethodField()
    aligned_image = serializers.SerializerMethodField()
    form_id = serializers.SerializerMethodField()

    class Meta:
        model = PageImage
        fields = ['id', 'page_number', 'image', 'processed_image', 'aligned_image', 
                  'status', 'processing_params', 'form_id', 'width', 'height', 'field_params', 'masking_params']

    def get_image(self, obj):
        return obj.image.url if obj.image else None

    def get_processed_image(self, obj):
        return obj.processed_image.url if obj.processed_image else None
    
    def get_aligned_image(self, obj):
        return obj.aligned_image.url if obj.aligned_image else None
    
    def get_form_id(self, obj):
        return obj.pdf.form_id if obj.pdf else None


class PatientDocumentSerializer(serializers.ModelSerializer):
    pages = PageImageSerializer(many=True, read_only=True)
    uploaded_by = serializers.StringRelatedField(read_only=True)  # or use a nested UserSerializer

    class Meta:
        model = PatientDocument
        fields = [
            'id',
            'file',
            'record_id',
            'record_type',
            #'uploaded_by',
            'uploaded_at',
            'status',
            'total_pages',
            'source_ip',
            'user_agent',
            'pages',
        ]
        read_only_fields = [
            'id',
            'uploaded_by',
            'uploaded_at',
            'status',
            'total_pages',
            'source_ip',
            'user_agent',
            'pages',
        ]

class GoogleAuthResponseSerializer(serializers.Serializer):
    sub = serializers.CharField()
    email = serializers.EmailField()
    email_verified = serializers.BooleanField()
    name = serializers.CharField()
    picture = serializers.URLField()
    given_name = serializers.CharField()
    family_name = serializers.CharField(required=False)


class CustomUserSerializer(serializers.ModelSerializer):

    # Return hospital and user_type IDs as integers
    hospital = serializers.SerializerMethodField()
    user_type = serializers.SerializerMethodField()
    # Add a computed full name field
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "hospital",
            "user_type",
        ]

    def get_hospital(self, obj):
        return obj.hospital.id if obj.hospital else None

    def get_user_type(self, obj):
        return obj.user_type.id if obj.user_type else None

    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()

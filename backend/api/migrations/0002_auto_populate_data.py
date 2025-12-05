from django.db import migrations

def create_default_document_types(apps, schema_editor):
    DocumentType = apps.get_model('api', 'DocumentType')

    defaults = [
        {"code": "NAR", "description": "Neonatal Admission Record"},
        {"code": "ITF", "description": "Internal Transfer Form"},
        {"code": "DSC", "description": "Discharge Summary Form"},
    ]

    for item in defaults:
        DocumentType.objects.get_or_create(code=item["code"], defaults=item)


def create_default_hospitals(apps, schema_editor):
    Hospital = apps.get_model('api', 'Hospital')

    defaults = [
        {"redcap_id": 17, "name": "Kenyatta National Hospital"},
        {"redcap_id": 52, "name": "Machakos Level 5 Hospital"},
        {"redcap_id": 53, "name": "Mama Lucy Kibaki Hospital"},
        {"redcap_id": 72, "name": "Pumwani Maternity Hospital"},
        {"redcap_id": 41, "name": "Thika Level 5 Hospital"},
        {"redcap_id": 40, "name": "Nakuru County Referral Hospital"},
        {"redcap_id": 63, "name": "Kakamega County General Teaching and Referral Hospital"},
        {"redcap_id": 76, "name": "Bungoma County Referral Hospital"},
    ]

    for item in defaults:
        Hospital.objects.get_or_create(redcap_id=item["redcap_id"], defaults=item)


def create_default_user_types(apps, schema_editor):
    UserType = apps.get_model('api', 'UserType')

    defaults = [
        {"code": "HRIO", "description": "Health Records Officer"},
        {"code": "DM", "description": "Program Data Manager"},
        {"code": "PLT", "description": "Pilot Tester"}
    ]

    for item in defaults:
        UserType.objects.get_or_create(code=item["code"], defaults=item)


def reverse_default_document_types(apps, schema_editor):
    DocumentType = apps.get_model('api', 'DocumentType')
    DocumentType.objects.filter(code__in=["NAR", "ITF", "DSC"]).delete()

def reverse_default_hospitals(apps, schema_editor):
    Hospital = apps.get_model('api', 'Hospital')
    Hospital.objects.filter(
        redcap_id__in=[17, 40, 41, 52, 53, 63, 72, 76]).delete()
    
def reverse_default_user_types(apps, schema_editor):
    UserType = apps.get_model('api', 'UserType')
    UserType.objects.filter(code__in=["HRIO", "DM", "PLT"]).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_default_document_types, reverse_default_document_types),
        migrations.RunPython(create_default_hospitals, reverse_default_hospitals),
        migrations.RunPython(create_default_user_types, reverse_default_user_types),
    ]
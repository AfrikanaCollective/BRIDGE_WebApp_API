from django.contrib import admin

from .models import Hospital, UserType, CustomUser, UserHospitalHistory, DocumentType, PatientDocument, PageImage, DocumentTransaction, PatientEncounter, TransactionTaskMap

#Register your models here
admin.site.register(Hospital)
admin.site.register(UserType)
admin.site.register(CustomUser)
admin.site.register(UserHospitalHistory)
admin.site.register(DocumentType)
admin.site.register(PatientEncounter)
admin.site.register(PatientDocument)
admin.site.register(PageImage)
admin.site.register(DocumentTransaction)
admin.site.register(TransactionTaskMap)
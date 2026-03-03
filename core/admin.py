from django.contrib import admin
from .models import GlobalConfig, Keyword, Tender, Attachment, Analysis, TenderManagement

# Registro simple de todos los modelos
admin.site.register(GlobalConfig)
admin.site.register(Keyword)
admin.site.register(Tender)
admin.site.register(Attachment)
admin.site.register(Analysis)
admin.site.register(TenderManagement)
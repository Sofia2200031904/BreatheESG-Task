from django.contrib import admin

from .models import AuditLog, Company, DataSource, NormalizedRecord, RawRecord, UploadBatch, ValidationIssue

admin.site.register(Company)
admin.site.register(DataSource)
admin.site.register(UploadBatch)
admin.site.register(RawRecord)
admin.site.register(NormalizedRecord)
admin.site.register(ValidationIssue)
admin.site.register(AuditLog)

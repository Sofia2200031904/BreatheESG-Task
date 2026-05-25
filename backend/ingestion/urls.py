from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AuditLogViewSet,
    CompanyViewSet,
    DataSourceViewSet,
    NormalizedRecordViewSet,
    SummaryView,
    UploadBatchViewSet,
    UploadCSVView,
)

router = DefaultRouter()
router.register("companies", CompanyViewSet)
router.register("data-sources", DataSourceViewSet)
router.register("batches", UploadBatchViewSet)
router.register("records", NormalizedRecordViewSet)
router.register("audit-logs", AuditLogViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("upload/", UploadCSVView.as_view(), name="upload-csv"),
    path("summary/", SummaryView.as_view(), name="summary"),
]

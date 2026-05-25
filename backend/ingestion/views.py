from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    AnalystReview,
    AuditLog,
    Company,
    DataSource,
    NormalizedRecord,
    RecordStatus,
    UploadBatch,
    ValidationIssue,
)
from .serializers import (
    AuditLogSerializer,
    CompanySerializer,
    DataSourceSerializer,
    EditRecordSerializer,
    NormalizedRecordSerializer,
    ReviewActionSerializer,
    UploadBatchSerializer,
    UploadSerializer,
)
from .services import ingest_csv_upload, recalculate_batch_counts


class TenantQuerysetMixin:
    company_field = "company"

    def get_company_id(self):
        return self.request.query_params.get("company_id") or self.request.headers.get("X-Company-ID")

    def get_queryset(self):
        queryset = super().get_queryset()
        company_id = self.get_company_id()
        if company_id:
            return queryset.filter(**{f"{self.company_field}_id": company_id})
        return queryset.none()


class CompanyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer


class DataSourceViewSet(TenantQuerysetMixin, viewsets.ModelViewSet):
    queryset = DataSource.objects.select_related("company").all()
    serializer_class = DataSourceSerializer


class UploadBatchViewSet(TenantQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = UploadBatch.objects.select_related("company", "data_source").all()
    serializer_class = UploadBatchSerializer


class NormalizedRecordViewSet(TenantQuerysetMixin, viewsets.ModelViewSet):
    queryset = (
        NormalizedRecord.objects.select_related("company", "batch", "batch__data_source", "raw_record")
        .prefetch_related("validation_issues", "reviews")
        .all()
    )
    serializer_class = NormalizedRecordSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.query_params.get("status")
        batch_id = self.request.query_params.get("batch_id")
        source_type = self.request.query_params.get("source_type")
        suspicious = self.request.query_params.get("suspicious")

        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if batch_id:
            queryset = queryset.filter(batch_id=batch_id)
        if source_type:
            queryset = queryset.filter(source_type=source_type)
        if suspicious == "true":
            queryset = queryset.filter(Q(status__in=[RecordStatus.WARNING, RecordStatus.FAILED]) | Q(validation_issues__is_resolved=False)).distinct()
        return queryset

    def partial_update(self, request, *args, **kwargs):
        record = self.get_object()
        if record.locked:
            return Response({"detail": "Approved records are locked for audit readiness."}, status=status.HTTP_423_LOCKED)

        serializer = EditRecordSerializer(record, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        actor = serializer.validated_data.pop("actor", "analyst")
        resolve_issues = serializer.validated_data.pop("resolve_issues", False)
        before = NormalizedRecordSerializer(record).data
        for field, value in serializer.validated_data.items():
            setattr(record, field, value)
        if resolve_issues:
            record.validation_issues.update(is_resolved=True)
            record.status = RecordStatus.VALID
        record.save()
        AuditLog.objects.create(
            company=record.company,
            batch=record.batch,
            raw_record=record.raw_record,
            normalized_record=record,
            action="record_edited",
            actor=actor,
            metadata={"before": before, "after": NormalizedRecordSerializer(record).data},
        )
        recalculate_batch_counts(record.batch)
        return Response(NormalizedRecordSerializer(record).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        record = self.get_object()
        serializer = ReviewActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        actor = serializer.validated_data["actor"]
        notes = serializer.validated_data.get("notes", "")
        if record.status == RecordStatus.FAILED and record.validation_issues.filter(severity=ValidationIssue.Severity.ERROR, is_resolved=False).exists():
            return Response({"detail": "Resolve failed validation issues before approval."}, status=status.HTTP_400_BAD_REQUEST)
        record.mark_approved(actor)
        AnalystReview.objects.create(normalized_record=record, reviewer=actor, decision=RecordStatus.APPROVED, notes=notes)
        AuditLog.objects.create(
            company=record.company,
            batch=record.batch,
            raw_record=record.raw_record,
            normalized_record=record,
            action="record_approved",
            actor=actor,
            metadata={"notes": notes},
        )
        recalculate_batch_counts(record.batch)
        return Response(NormalizedRecordSerializer(record).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        record = self.get_object()
        if record.locked:
            return Response({"detail": "Approved records are locked for audit readiness."}, status=status.HTTP_423_LOCKED)
        serializer = ReviewActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        actor = serializer.validated_data["actor"]
        notes = serializer.validated_data.get("notes", "")
        record.status = RecordStatus.REJECTED
        record.save(update_fields=["status", "updated_at"])
        AnalystReview.objects.create(normalized_record=record, reviewer=actor, decision=RecordStatus.REJECTED, notes=notes)
        AuditLog.objects.create(
            company=record.company,
            batch=record.batch,
            raw_record=record.raw_record,
            normalized_record=record,
            action="record_rejected",
            actor=actor,
            metadata={"notes": notes},
        )
        recalculate_batch_counts(record.batch)
        return Response(NormalizedRecordSerializer(record).data)


class AuditLogViewSet(TenantQuerysetMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = AuditLog.objects.select_related("company", "batch", "raw_record", "normalized_record").all()
    serializer_class = AuditLogSerializer


class UploadCSVView(APIView):
    def post(self, request):
        serializer = UploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company = get_object_or_404(Company, pk=serializer.validated_data["company_id"])
        data_source = get_object_or_404(
            DataSource, pk=serializer.validated_data["data_source_id"], company=company
        )
        batch = ingest_csv_upload(
            company=company,
            data_source=data_source,
            uploaded_file=serializer.validated_data["file"],
            uploaded_by=serializer.validated_data.get("uploaded_by") or "analyst",
        )
        return Response(UploadBatchSerializer(batch).data, status=status.HTTP_201_CREATED)


class SummaryView(APIView):
    def get(self, request):
        company_id = request.query_params.get("company_id") or request.headers.get("X-Company-ID")
        if not company_id:
            return Response({"detail": "company_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        records = NormalizedRecord.objects.filter(company_id=company_id)
        return Response(
            {
                "batches": UploadBatch.objects.filter(company_id=company_id).count(),
                "records": records.count(),
                "co2e_kg": records.aggregate(total=Sum("co2e_kg"))["total"] or 0,
                "by_status": list(records.values("status").annotate(count=Count("id")).order_by("status")),
                "by_scope": list(records.values("scope").annotate(count=Count("id"), co2e_kg=Sum("co2e_kg")).order_by("scope")),
                "open_issues": ValidationIssue.objects.filter(
                    normalized_record__company_id=company_id, is_resolved=False
                ).count(),
            }
        )

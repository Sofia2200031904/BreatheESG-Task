from rest_framework import serializers

from .models import (
    AnalystReview,
    AuditLog,
    Company,
    DataSource,
    NormalizedRecord,
    RawRecord,
    UploadBatch,
    ValidationIssue,
)


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ["id", "name", "slug", "created_at"]


class DataSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSource
        fields = ["id", "company", "name", "source_type", "description", "created_at"]


class UploadBatchSerializer(serializers.ModelSerializer):
    data_source_name = serializers.CharField(source="data_source.name", read_only=True)
    source_type = serializers.CharField(source="data_source.source_type", read_only=True)

    class Meta:
        model = UploadBatch
        fields = [
            "id",
            "company",
            "data_source",
            "data_source_name",
            "source_type",
            "original_filename",
            "uploaded_by",
            "created_at",
            "status",
            "total_rows",
            "valid_rows",
            "warning_rows",
            "failed_rows",
            "approved_rows",
        ]


class RawRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawRecord
        fields = ["id", "row_number", "source_row_hash", "raw_data", "uploaded_at", "status"]


class ValidationIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = ValidationIssue
        fields = ["id", "rule_code", "severity", "message", "field", "created_at", "is_resolved"]


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ["id", "batch", "raw_record", "normalized_record", "action", "actor", "metadata", "created_at"]


class AnalystReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalystReview
        fields = ["id", "reviewer", "decision", "notes", "created_at"]


class NormalizedRecordSerializer(serializers.ModelSerializer):
    raw_record = RawRecordSerializer(read_only=True)
    validation_issues = ValidationIssueSerializer(many=True, read_only=True)
    reviews = AnalystReviewSerializer(many=True, read_only=True)
    source_name = serializers.CharField(source="batch.data_source.name", read_only=True)
    batch_filename = serializers.CharField(source="batch.original_filename", read_only=True)

    class Meta:
        model = NormalizedRecord
        fields = [
            "id",
            "raw_record",
            "company",
            "batch",
            "batch_filename",
            "source_name",
            "source_type",
            "scope",
            "activity_date",
            "period_start",
            "period_end",
            "facility_code",
            "category",
            "subcategory",
            "quantity",
            "unit",
            "co2e_kg",
            "normalized_data",
            "status",
            "duplicate_key",
            "approved_by",
            "approved_at",
            "locked",
            "updated_at",
            "validation_issues",
            "reviews",
        ]
        read_only_fields = ["company", "batch", "raw_record", "source_type", "duplicate_key", "approved_by", "approved_at"]


class UploadSerializer(serializers.Serializer):
    company_id = serializers.IntegerField()
    data_source_id = serializers.IntegerField()
    uploaded_by = serializers.CharField(required=False, allow_blank=True, default="analyst")
    file = serializers.FileField()


class ReviewActionSerializer(serializers.Serializer):
    actor = serializers.CharField(default="analyst")
    notes = serializers.CharField(required=False, allow_blank=True)


class EditRecordSerializer(serializers.ModelSerializer):
    actor = serializers.CharField(write_only=True, default="analyst")
    resolve_issues = serializers.BooleanField(write_only=True, default=False)

    class Meta:
        model = NormalizedRecord
        fields = [
            "activity_date",
            "period_start",
            "period_end",
            "facility_code",
            "category",
            "subcategory",
            "quantity",
            "unit",
            "co2e_kg",
            "normalized_data",
            "actor",
            "resolve_issues",
        ]

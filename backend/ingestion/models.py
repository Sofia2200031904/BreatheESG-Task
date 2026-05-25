from django.db import models
from django.utils import timezone


class Company(models.Model):
    name = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class SourceType(models.TextChoices):
    SAP_FUEL_PROCUREMENT = "sap_fuel_procurement", "SAP fuel and procurement"
    UTILITY_ELECTRICITY = "utility_electricity", "Utility electricity"
    CORPORATE_TRAVEL = "corporate_travel", "Corporate travel"


class RecordStatus(models.TextChoices):
    VALID = "valid", "Valid"
    WARNING = "warning", "Warning"
    FAILED = "failed", "Failed"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class Scope(models.TextChoices):
    SCOPE_1 = "scope_1", "Scope 1"
    SCOPE_2 = "scope_2", "Scope 2"
    SCOPE_3 = "scope_3", "Scope 3"


class DataSource(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="data_sources")
    name = models.CharField(max_length=180)
    source_type = models.CharField(max_length=40, choices=SourceType.choices)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("company", "source_type")]
        ordering = ["company", "name"]

    def __str__(self):
        return f"{self.company}: {self.name}"


class UploadBatch(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="upload_batches")
    data_source = models.ForeignKey(DataSource, on_delete=models.PROTECT, related_name="upload_batches")
    original_filename = models.CharField(max_length=255)
    uploaded_by = models.CharField(max_length=180, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=RecordStatus.choices, default=RecordStatus.VALID)
    total_rows = models.PositiveIntegerField(default=0)
    valid_rows = models.PositiveIntegerField(default=0)
    warning_rows = models.PositiveIntegerField(default=0)
    failed_rows = models.PositiveIntegerField(default=0)
    approved_rows = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.original_filename} ({self.company})"


class RawRecord(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="raw_records")
    batch = models.ForeignKey(UploadBatch, on_delete=models.CASCADE, related_name="raw_records")
    row_number = models.PositiveIntegerField()
    source_row_hash = models.CharField(max_length=64, db_index=True)
    raw_data = models.JSONField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=RecordStatus.choices, default=RecordStatus.VALID)

    class Meta:
        unique_together = [("batch", "row_number")]
        ordering = ["batch", "row_number"]

    def __str__(self):
        return f"Raw row {self.row_number} in batch {self.batch_id}"


class NormalizedRecord(models.Model):
    raw_record = models.OneToOneField(RawRecord, on_delete=models.CASCADE, related_name="normalized_record")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="normalized_records")
    batch = models.ForeignKey(UploadBatch, on_delete=models.CASCADE, related_name="normalized_records")
    source_type = models.CharField(max_length=40, choices=SourceType.choices)
    scope = models.CharField(max_length=20, choices=Scope.choices)
    activity_date = models.DateField(null=True, blank=True)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    facility_code = models.CharField(max_length=80, blank=True)
    category = models.CharField(max_length=120)
    subcategory = models.CharField(max_length=120, blank=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    unit = models.CharField(max_length=40)
    co2e_kg = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    normalized_data = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=RecordStatus.choices, default=RecordStatus.VALID)
    duplicate_key = models.CharField(max_length=255, blank=True, db_index=True)
    approved_by = models.CharField(max_length=180, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    locked = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-batch__created_at", "raw_record__row_number"]
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["company", "scope"]),
            models.Index(fields=["company", "source_type"]),
        ]

    def mark_approved(self, actor):
        self.status = RecordStatus.APPROVED
        self.approved_by = actor
        self.approved_at = timezone.now()
        self.locked = True
        self.save(update_fields=["status", "approved_by", "approved_at", "locked", "updated_at"])

    def __str__(self):
        return f"{self.source_type} row {self.raw_record.row_number}"


class ValidationIssue(models.Model):
    class Severity(models.TextChoices):
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"

    normalized_record = models.ForeignKey(NormalizedRecord, on_delete=models.CASCADE, related_name="validation_issues")
    rule_code = models.CharField(max_length=80)
    severity = models.CharField(max_length=20, choices=Severity.choices)
    message = models.TextField()
    field = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ["normalized_record_id", "-severity", "rule_code"]

    def __str__(self):
        return f"{self.rule_code}: {self.message}"


class AnalystReview(models.Model):
    normalized_record = models.ForeignKey(NormalizedRecord, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.CharField(max_length=180)
    decision = models.CharField(max_length=20, choices=RecordStatus.choices)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class AuditLog(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="audit_logs")
    batch = models.ForeignKey(UploadBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    raw_record = models.ForeignKey(RawRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    normalized_record = models.ForeignKey(
        NormalizedRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs"
    )
    action = models.CharField(max_length=80)
    actor = models.CharField(max_length=180, blank=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} at {self.created_at:%Y-%m-%d %H:%M}"

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .models import Company, DataSource, NormalizedRecord, RecordStatus, SourceType
from .services import ingest_csv_upload


class IngestionPipelineTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Test Co", slug="test-co")
        self.sap_source = DataSource.objects.create(
            company=self.company,
            name="SAP",
            source_type=SourceType.SAP_FUEL_PROCUREMENT,
        )
        self.utility_source = DataSource.objects.create(
            company=self.company,
            name="Utility",
            source_type=SourceType.UTILITY_ELECTRICITY,
        )
        self.travel_source = DataSource.objects.create(
            company=self.company,
            name="Travel",
            source_type=SourceType.CORPORATE_TRAVEL,
        )

    def test_sap_mixed_units_are_normalized_and_scoped(self):
        upload = SimpleUploadedFile(
            "sap.csv",
            b"Posting Date,Plant Code,Procurement Category,Qty,UoM\n2026-01-02,PLT-1,Diesel fuel,10,gallons\n",
            content_type="text/csv",
        )

        batch = ingest_csv_upload(self.company, self.sap_source, upload)
        record = NormalizedRecord.objects.get(batch=batch)

        self.assertEqual(record.scope, "scope_1")
        self.assertEqual(record.unit, "L")
        self.assertEqual(str(record.quantity), "37.8541")
        self.assertEqual(record.status, RecordStatus.VALID)

    def test_utility_non_calendar_period_warns(self):
        upload = SimpleUploadedFile(
            "utility.csv",
            b"Billing Start,Billing End,Meter ID,Tariff,Usage,Unit\n2026-01-18,2026-02-17,MTR-1,TOU,1,MWh\n",
            content_type="text/csv",
        )

        batch = ingest_csv_upload(self.company, self.utility_source, upload)
        record = NormalizedRecord.objects.get(batch=batch)

        self.assertEqual(record.scope, "scope_2")
        self.assertEqual(str(record.quantity), "1000.0000")
        self.assertEqual(record.status, RecordStatus.WARNING)
        self.assertTrue(record.validation_issues.filter(rule_code="non_calendar_billing_period").exists())

    def test_impossible_travel_distance_fails(self):
        upload = SimpleUploadedFile(
            "travel.csv",
            b"Travel Date,Traveler,Expense Type,origin_airport,destination_airport,Flight Class,distance_km\n2026-01-02,Ana,Flight,JFK,LHR,Economy,27000\n",
            content_type="text/csv",
        )

        batch = ingest_csv_upload(self.company, self.travel_source, upload)
        record = NormalizedRecord.objects.get(batch=batch)

        self.assertEqual(record.scope, "scope_3")
        self.assertEqual(record.status, RecordStatus.FAILED)
        self.assertTrue(record.validation_issues.filter(rule_code="impossible_travel_distance").exists())

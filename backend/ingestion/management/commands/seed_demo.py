from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand

from ingestion.models import Company, DataSource, SourceType
from ingestion.services import ingest_csv_upload


class Command(BaseCommand):
    help = "Create demo companies, data sources, and optionally ingest bundled messy CSV samples."

    def add_arguments(self, parser):
        parser.add_argument("--load-samples", action="store_true", help="Ingest sample CSV files into the first demo company.")

    def handle(self, *args, **options):
        acme, _ = Company.objects.get_or_create(name="Acme Manufacturing", slug="acme-manufacturing")
        northwind, _ = Company.objects.get_or_create(name="Northwind Retail", slug="northwind-retail")

        for company in (acme, northwind):
            DataSource.objects.get_or_create(
                company=company,
                source_type=SourceType.SAP_FUEL_PROCUREMENT,
                defaults={
                    "name": "SAP Fuel & Procurement Export",
                    "description": "Flat-file SAP-style plant fuel and procurement line items.",
                },
            )
            DataSource.objects.get_or_create(
                company=company,
                source_type=SourceType.UTILITY_ELECTRICITY,
                defaults={
                    "name": "Utility Portal Electricity Bills",
                    "description": "Meter-level electricity CSVs with non-calendar billing periods.",
                },
            )
            DataSource.objects.get_or_create(
                company=company,
                source_type=SourceType.CORPORATE_TRAVEL,
                defaults={
                    "name": "Corporate Travel Export",
                    "description": "Concur/Navan-like flights, hotels, taxis, and trains.",
                },
            )

        if options["load_samples"]:
            samples = {
                SourceType.SAP_FUEL_PROCUREMENT: "sap_fuel_procurement.csv",
                SourceType.UTILITY_ELECTRICITY: "utility_electricity.csv",
                SourceType.CORPORATE_TRAVEL: "corporate_travel.csv",
            }
            sample_dir = Path(__file__).resolve().parents[3] / "sample_data"
            for company in (acme, northwind):
                if company.upload_batches.exists():
                    continue
                for source_type, filename in samples.items():
                    data_source = DataSource.objects.get(company=company, source_type=source_type)
                    with (sample_dir / filename).open("rb") as handle:
                        ingest_csv_upload(company, data_source, File(handle, name=filename), uploaded_by="demo.seed")

        self.stdout.write(self.style.SUCCESS("Demo tenant data is ready."))

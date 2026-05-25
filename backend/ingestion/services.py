import csv
import hashlib
import io
import math
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from dateutil import parser
from django.db import transaction

from .models import (
    AuditLog,
    DataSource,
    NormalizedRecord,
    RawRecord,
    RecordStatus,
    Scope,
    SourceType,
    UploadBatch,
    ValidationIssue,
)


LIQUID_TO_LITERS = {
    "l": Decimal("1"),
    "liter": Decimal("1"),
    "liters": Decimal("1"),
    "litre": Decimal("1"),
    "litres": Decimal("1"),
    "gal": Decimal("3.78541"),
    "gallon": Decimal("3.78541"),
    "gallons": Decimal("3.78541"),
}

MASS_TO_METRIC_TONS = {
    "t": Decimal("1"),
    "ton": Decimal("0.907185"),
    "tons": Decimal("0.907185"),
    "tonne": Decimal("1"),
    "tonnes": Decimal("1"),
    "metric ton": Decimal("1"),
    "metric tons": Decimal("1"),
    "kg": Decimal("0.001"),
}

ELECTRICITY_TO_KWH = {
    "kwh": Decimal("1"),
    "kw h": Decimal("1"),
    "mwh": Decimal("1000"),
}

FUEL_FACTORS_KG_PER_LITER = {
    "diesel": Decimal("2.68"),
    "gasoline": Decimal("2.31"),
    "petrol": Decimal("2.31"),
    "fuel oil": Decimal("3.05"),
}

AIRPORTS = {
    "ATL": (33.6407, -84.4277),
    "BLR": (13.1986, 77.7066),
    "BOM": (19.0896, 72.8656),
    "CDG": (49.0097, 2.5479),
    "DEL": (28.5562, 77.1000),
    "DXB": (25.2532, 55.3657),
    "FRA": (50.0379, 8.5622),
    "JFK": (40.6413, -73.7781),
    "LAX": (33.9416, -118.4085),
    "LHR": (51.4700, -0.4543),
    "SFO": (37.6213, -122.3790),
    "SIN": (1.3644, 103.9915),
}

FLIGHT_FACTORS = {
    "economy": Decimal("0.12"),
    "premium economy": Decimal("0.15"),
    "business": Decimal("0.18"),
    "first": Decimal("0.24"),
}


@dataclass
class NormalizationResult:
    scope: str
    activity_date: date | None
    period_start: date | None
    period_end: date | None
    facility_code: str
    category: str
    subcategory: str
    quantity: Decimal | None
    unit: str
    co2e_kg: Decimal | None
    normalized_data: dict
    duplicate_key: str
    issues: list[dict] = field(default_factory=list)


def ingest_csv_upload(company, data_source, uploaded_file, uploaded_by="analyst"):
    text = uploaded_file.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    with transaction.atomic():
        batch = UploadBatch.objects.create(
            company=company,
            data_source=data_source,
            original_filename=getattr(uploaded_file, "name", "upload.csv"),
            uploaded_by=uploaded_by,
        )

        seen_duplicate_keys = set()
        for row_number, row in enumerate(reader, start=2):
            cleaned_row = {str(key).strip(): (value.strip() if isinstance(value, str) else value) for key, value in row.items()}
            raw_record = RawRecord.objects.create(
                company=company,
                batch=batch,
                row_number=row_number,
                source_row_hash=hash_row(cleaned_row),
                raw_data=cleaned_row,
            )
            result = normalize_row(data_source.source_type, cleaned_row)
            normalized_record = NormalizedRecord.objects.create(
                raw_record=raw_record,
                company=company,
                batch=batch,
                source_type=data_source.source_type,
                scope=result.scope,
                activity_date=result.activity_date,
                period_start=result.period_start,
                period_end=result.period_end,
                facility_code=result.facility_code,
                category=result.category,
                subcategory=result.subcategory,
                quantity=result.quantity,
                unit=result.unit,
                co2e_kg=result.co2e_kg,
                normalized_data=result.normalized_data,
                duplicate_key=result.duplicate_key,
            )

            if result.duplicate_key in seen_duplicate_keys or NormalizedRecord.objects.filter(
                company=company, duplicate_key=result.duplicate_key
            ).exclude(pk=normalized_record.pk).exists():
                result.issues.append(
                    {
                        "rule_code": "duplicate_record",
                        "severity": ValidationIssue.Severity.ERROR,
                        "message": "A record with the same source, date/period, facility, category and quantity already exists.",
                        "field": "duplicate_key",
                    }
                )
            seen_duplicate_keys.add(result.duplicate_key)

            apply_issues(normalized_record, result.issues)
            raw_record.status = normalized_record.status
            raw_record.save(update_fields=["status"])

            AuditLog.objects.create(
                company=company,
                batch=batch,
                raw_record=raw_record,
                normalized_record=normalized_record,
                action="record_ingested",
                actor=uploaded_by,
                metadata={"source_type": data_source.source_type, "row_number": row_number},
            )

        recalculate_batch_counts(batch)
        AuditLog.objects.create(
            company=company,
            batch=batch,
            action="batch_uploaded",
            actor=uploaded_by,
            metadata={"filename": batch.original_filename, "total_rows": batch.total_rows},
        )
        return batch


def normalize_row(source_type, row):
    if source_type == SourceType.SAP_FUEL_PROCUREMENT:
        return normalize_sap(row)
    if source_type == SourceType.UTILITY_ELECTRICITY:
        return normalize_utility(row)
    if source_type == SourceType.CORPORATE_TRAVEL:
        return normalize_travel(row)
    raise ValueError(f"Unsupported source type: {source_type}")


def normalize_sap(row):
    issues = []
    activity_date = parse_date(first(row, "posting_date", "Posting Date", "Doc Date", "Date"), issues, "posting_date")
    plant = first(row, "plant", "Plant", "Plant Code", "plant_code")
    category = first(row, "category", "Procurement Category", "Material Group", "material")
    quantity = parse_decimal(first(row, "quantity", "Qty", "Amount", "usage"), issues, "quantity")
    unit_raw = normalize_unit(first(row, "unit", "UoM", "Unit", "Base Unit"))

    if not plant:
        add_issue(issues, "missing_required_field", "error", "Plant code is required for SAP rows.", "plant")
    if not category:
        add_issue(issues, "missing_required_field", "error", "Procurement category or fuel type is required.", "category")
    if quantity is None:
        add_issue(issues, "missing_required_field", "error", "Quantity is required.", "quantity")
    elif quantity < 0:
        add_issue(issues, "negative_usage", "error", "SAP usage or procurement quantity cannot be negative.", "quantity")
    elif quantity > Decimal("1000000"):
        add_issue(issues, "suspicious_value", "warning", "Quantity is unusually high for a single SAP line.", "quantity")

    category_key = category.lower()
    is_fuel = any(name in category_key for name in FUEL_FACTORS_KG_PER_LITER) or "fuel" in category_key
    if is_fuel:
        std_quantity, std_unit = convert_liquid(quantity, unit_raw, issues)
        factor = next((value for key, value in FUEL_FACTORS_KG_PER_LITER.items() if key in category_key), Decimal("2.50"))
        co2e_kg = safe_multiply(std_quantity, factor)
        scope = Scope.SCOPE_1
    else:
        std_quantity, std_unit = convert_mass(quantity, unit_raw, issues)
        co2e_kg = safe_multiply(std_quantity, Decimal("500"))
        scope = Scope.SCOPE_3

    duplicate_key = make_duplicate_key("sap", activity_date, plant, category, std_quantity, std_unit)
    return NormalizationResult(
        scope=scope,
        activity_date=activity_date,
        period_start=None,
        period_end=None,
        facility_code=plant,
        category=category or "Unknown procurement",
        subcategory=first(row, "vendor", "Vendor", "Supplier"),
        quantity=std_quantity,
        unit=std_unit,
        co2e_kg=co2e_kg,
        normalized_data={"source": "SAP", "unit_original": unit_raw, "plant_code": plant},
        duplicate_key=duplicate_key,
        issues=issues,
    )


def normalize_utility(row):
    issues = []
    period_start = parse_date(first(row, "billing_start", "Billing Start", "Period From", "start_date"), issues, "period_start")
    period_end = parse_date(first(row, "billing_end", "Billing End", "Period To", "end_date"), issues, "period_end")
    meter_id = first(row, "meter_id", "Meter ID", "Meter", "meter")
    tariff = first(row, "tariff", "Tariff", "Rate Plan", "tariff_name")
    usage = parse_decimal(first(row, "usage", "Usage", "electricity", "kwh", "MWh"), issues, "usage")
    unit_raw = normalize_unit(first(row, "unit", "Unit", "usage_unit", "UOM"))

    if not meter_id:
        add_issue(issues, "missing_required_field", "error", "Meter ID is required.", "meter_id")
    if usage is None:
        add_issue(issues, "missing_required_field", "error", "Electricity usage is required.", "usage")
    elif usage < 0:
        add_issue(issues, "negative_usage", "error", "Electricity usage cannot be negative.", "usage")
    elif usage > Decimal("5000000"):
        add_issue(issues, "suspicious_value", "warning", "Electricity usage is unusually high for one bill.", "usage")
    if period_start and period_end and period_end < period_start:
        add_issue(issues, "invalid_date_range", "error", "Billing period end is before the start date.", "period_end")
    if period_start and period_end and period_start.month != period_end.month:
        add_issue(
            issues,
            "non_calendar_billing_period",
            "warning",
            "Billing period crosses calendar months and may need allocation during reporting.",
            "period_start",
        )

    std_usage, std_unit = convert_electricity(usage, unit_raw, issues)
    co2e_kg = safe_multiply(std_usage, Decimal("0.38"))
    activity_date = period_end or period_start
    duplicate_key = make_duplicate_key("utility", period_start, period_end, meter_id, std_usage, std_unit)
    return NormalizationResult(
        scope=Scope.SCOPE_2,
        activity_date=activity_date,
        period_start=period_start,
        period_end=period_end,
        facility_code=meter_id,
        category="Purchased electricity",
        subcategory=tariff,
        quantity=std_usage,
        unit=std_unit,
        co2e_kg=co2e_kg,
        normalized_data={"source": "Utility portal", "tariff": tariff, "unit_original": unit_raw},
        duplicate_key=duplicate_key,
        issues=issues,
    )


def normalize_travel(row):
    issues = []
    travel_date = parse_date(first(row, "date", "Travel Date", "Expense Date", "booking_date"), issues, "date")
    category = first(row, "category", "Expense Type", "Travel Type", "type").lower()
    traveler = first(row, "traveler", "Employee", "employee_name")
    origin = first(row, "origin", "From", "origin_airport").upper()
    destination = first(row, "destination", "To", "destination_airport").upper()
    travel_class = first(row, "class", "Flight Class", "Cabin", "flight_class").lower() or "economy"
    distance = parse_decimal(first(row, "distance_km", "Distance KM", "distance", "Miles"), [], "distance")
    nights = parse_decimal(first(row, "nights", "Hotel Nights", "hotel_nights"), [], "nights")

    if not category:
        add_issue(issues, "missing_required_field", "error", "Travel category is required.", "category")
    if not traveler:
        add_issue(issues, "missing_required_field", "warning", "Traveler is missing; record can be reviewed but attribution is weaker.", "traveler")

    if "flight" in category:
        if distance is None and origin in AIRPORTS and destination in AIRPORTS:
            distance = Decimal(str(round(haversine_km(AIRPORTS[origin], AIRPORTS[destination]), 2)))
        elif distance is None:
            add_issue(issues, "missing_distance", "warning", "Flight distance is missing and airport pair is not in reference map.", "distance_km")
        if not origin or not destination:
            add_issue(issues, "missing_required_field", "error", "Flight origin and destination airport codes are required.", "origin")
        factor = FLIGHT_FACTORS.get(travel_class, FLIGHT_FACTORS["economy"])
        std_quantity = distance
        std_unit = "km"
        co2e_kg = safe_multiply(std_quantity, factor)
        subcategory = travel_class
    elif "hotel" in category:
        if nights is None:
            add_issue(issues, "missing_required_field", "error", "Hotel nights are required for hotel stay rows.", "nights")
        std_quantity = nights
        std_unit = "nights"
        co2e_kg = safe_multiply(std_quantity, Decimal("25"))
        subcategory = first(row, "city", "Hotel City", "location")
    elif "train" in category:
        std_quantity = distance
        std_unit = "km"
        co2e_kg = safe_multiply(std_quantity, Decimal("0.041"))
        subcategory = "rail"
    else:
        std_quantity = distance
        std_unit = "km"
        co2e_kg = safe_multiply(std_quantity, Decimal("0.18"))
        subcategory = category or "ground"

    if std_quantity is not None:
        if std_quantity < 0:
            add_issue(issues, "negative_usage", "error", "Travel distance or nights cannot be negative.", "distance_km")
        if std_unit == "km" and std_quantity > Decimal("22000"):
            add_issue(issues, "impossible_travel_distance", "error", "Travel distance exceeds a plausible single trip distance.", "distance_km")
        elif std_unit == "km" and std_quantity > Decimal("15000"):
            add_issue(issues, "suspicious_value", "warning", "Travel distance is unusually long and should be reviewed.", "distance_km")

    duplicate_key = make_duplicate_key("travel", travel_date, traveler, category, origin, destination, std_quantity)
    return NormalizationResult(
        scope=Scope.SCOPE_3,
        activity_date=travel_date,
        period_start=None,
        period_end=None,
        facility_code=origin if origin else first(row, "cost_center", "Cost Center"),
        category=category.title() if category else "Travel",
        subcategory=subcategory,
        quantity=std_quantity,
        unit=std_unit,
        co2e_kg=co2e_kg,
        normalized_data={"source": "Corporate travel", "origin": origin, "destination": destination, "traveler": traveler},
        duplicate_key=duplicate_key,
        issues=issues,
    )


def apply_issues(normalized_record, issues):
    has_error = any(issue["severity"] == ValidationIssue.Severity.ERROR for issue in issues)
    has_warning = any(issue["severity"] == ValidationIssue.Severity.WARNING for issue in issues)
    normalized_record.status = RecordStatus.FAILED if has_error else RecordStatus.WARNING if has_warning else RecordStatus.VALID
    normalized_record.save(update_fields=["status"])

    for issue in issues:
        ValidationIssue.objects.create(normalized_record=normalized_record, **issue)


def recalculate_batch_counts(batch):
    records = NormalizedRecord.objects.filter(batch=batch)
    batch.total_rows = records.count()
    batch.valid_rows = records.filter(status=RecordStatus.VALID).count()
    batch.warning_rows = records.filter(status=RecordStatus.WARNING).count()
    batch.failed_rows = records.filter(status=RecordStatus.FAILED).count()
    batch.approved_rows = records.filter(status=RecordStatus.APPROVED).count()
    batch.status = RecordStatus.FAILED if batch.failed_rows else RecordStatus.WARNING if batch.warning_rows else RecordStatus.VALID
    batch.save(
        update_fields=["total_rows", "valid_rows", "warning_rows", "failed_rows", "approved_rows", "status"]
    )


def parse_date(value, issues, field_name):
    if not value:
        add_issue(issues, "missing_required_field", "error", f"{field_name} is required.", field_name)
        return None
    try:
        return parser.parse(str(value), dayfirst=False, fuzzy=False).date()
    except (ValueError, TypeError, OverflowError):
        add_issue(issues, "invalid_date", "error", f"Could not parse date value '{value}'.", field_name)
        return None


def parse_decimal(value, issues, field_name):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        add_issue(issues, "invalid_number", "error", f"Could not parse numeric value '{value}'.", field_name)
        return None


def convert_liquid(quantity, unit, issues):
    if quantity is None:
        return None, "L"
    if unit in LIQUID_TO_LITERS:
        return (quantity * LIQUID_TO_LITERS[unit]).quantize(Decimal("0.0001")), "L"
    add_issue(issues, "unknown_unit", "error", f"Unknown liquid fuel unit '{unit}'.", "unit")
    return quantity, unit or "unknown"


def convert_mass(quantity, unit, issues):
    if quantity is None:
        return None, "metric_ton"
    if unit in MASS_TO_METRIC_TONS:
        return (quantity * MASS_TO_METRIC_TONS[unit]).quantize(Decimal("0.0001")), "metric_ton"
    add_issue(issues, "unknown_unit", "warning", f"Unknown procurement unit '{unit}', preserving original quantity.", "unit")
    return quantity, unit or "unknown"


def convert_electricity(quantity, unit, issues):
    if quantity is None:
        return None, "kWh"
    if unit in ELECTRICITY_TO_KWH:
        return (quantity * ELECTRICITY_TO_KWH[unit]).quantize(Decimal("0.0001")), "kWh"
    add_issue(issues, "unknown_unit", "error", f"Unknown electricity unit '{unit}'.", "unit")
    return quantity, unit or "unknown"


def first(row, *names):
    lowered = {key.lower().strip(): value for key, value in row.items()}
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return str(value).strip()
        value = lowered.get(name.lower())
        if value not in (None, ""):
            return str(value).strip()
    return ""


def normalize_unit(unit):
    return str(unit or "").strip().lower().replace(".", "")


def add_issue(issues, rule_code, severity, message, field):
    issues.append({"rule_code": rule_code, "severity": severity, "message": message, "field": field})


def safe_multiply(quantity, factor):
    if quantity is None:
        return None
    return (quantity * factor).quantize(Decimal("0.0001"))


def hash_row(row):
    serialized = "|".join(f"{key}={row[key]}" for key in sorted(row))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def make_duplicate_key(*parts):
    normalized = "|".join(str(part or "").strip().lower() for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def haversine_km(point_a, point_b):
    lat1, lon1 = map(math.radians, point_a)
    lat2, lon2 = map(math.radians, point_b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))

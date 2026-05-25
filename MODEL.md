# Data Model

The schema is centered on auditability: each uploaded source row is preserved as raw JSON, then linked one-to-one to a normalized ESG record.

## Tenant model

- `Company` owns all data.
- `DataSource` belongs to one company and identifies one source type: SAP fuel/procurement, utility electricity, or corporate travel.
- Every batch, raw row, normalized row, validation issue, review, and audit log is reachable from a company. API list endpoints require `company_id` or `X-Company-ID` so tenants do not see one another's data.

## Ingestion model

- `UploadBatch` represents one CSV upload. It stores source, filename, uploader, status, and row counts.
- `RawRecord` stores row number, SHA-256 row hash, upload timestamp, raw JSON, and status.
- `NormalizedRecord` stores the internal ESG schema: source type, scope, activity date or billing period, facility or meter code, category, quantity, standardized unit, estimated CO2e, status, approval metadata, lock state, and duplicate key.

## Quality and review model

- `ValidationIssue` stores explainable rule failures or warnings per normalized row.
- `AnalystReview` stores approval or rejection decisions and notes.
- `AuditLog` records ingestion, edit, approval, rejection, and batch events with actor and structured metadata.

## Why raw and normalized records are separate

Auditors need to compare the source row to the transformed row. Keeping both records avoids overwriting evidence and makes every correction traceable through `AuditLog`.

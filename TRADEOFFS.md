# Tradeoffs

- No authentication: tenant filtering is simulated with `company_id`; production would use authenticated users, roles, and organization membership.
- No real external integrations: SAP, utility portals, and travel providers are represented by realistic CSV exports only.
- No OCR or document parsing: invoices and PDFs are out of scope.
- No advanced emissions factor engine: factors are simple constants to keep focus on data quality, normalization, and audit trail.
- No asynchronous job queue: uploads are processed synchronously, which is suitable for demo CSVs but not enterprise files with millions of rows.
- No formal month allocation: utility bills that cross calendar months are flagged, not split into monthly reporting buckets.
- No deployment was performed from this environment because live hosting and GitHub push require account credentials.

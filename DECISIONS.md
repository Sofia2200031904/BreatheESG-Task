# Decisions

- The app uses deterministic normalization instead of AI extraction because the task is about explainable ingestion and audit review.
- CSV upload is the only integration surface. Real SAP, utility, and travel APIs were intentionally skipped to keep the system demonstrable and testable.
- PostgreSQL is the production database target, while SQLite fallback keeps local review fast when Postgres is not running.
- Tenant isolation is modeled at the database and API-query level. A production system would add SSO, role-based authorization, and database row-level security.
- Emission factors are simplified placeholders. The code records normalized activity data and CO2e estimates, but real deployments should plug in region, supplier, fuel, and reporting-year factor libraries.
- Approved records become locked. Analysts must edit and resolve issues before approval so the approved dataset remains stable for audit export.
- Non-calendar utility billing periods are warnings instead of failures because they are common in real bills and usually need allocation rather than rejection.

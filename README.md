# ESG Data Ingestion and Audit Review Platform

Full-stack demo of an enterprise ESG ingestion workflow for messy SAP, utility, and corporate travel data. The backend is Django REST Framework with PostgreSQL support; the frontend is React and Tailwind CSS.

## What it does

- Upload CSV exports for SAP fuel/procurement, utility electricity bills, and corporate travel.
- Preserve every raw row, normalize it into a unified ESG schema, and classify it into Scope 1, Scope 2, or Scope 3.
- Detect invalid dates, missing fields, duplicates, negative values, suspicious quantities, non-calendar utility periods, and impossible travel distances.
- Let analysts filter, inspect raw vs normalized data, edit values, approve/reject records, and lock approved rows for audit readiness.
- Scope every source, batch, record, issue, and audit event to a company tenant.

## Local setup

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo --load-samples
python manage.py runserver 127.0.0.1:8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## PostgreSQL

The backend uses `DATABASE_URL` when present and falls back to SQLite for quick local checks. To run local PostgreSQL:

```bash
docker compose up -d
set DATABASE_URL=postgres://esg:esg@localhost:5432/esg_platform
```

## Sample CSVs

Bundled samples live in `backend/sample_data/`:

- `sap_fuel_procurement.csv`
- `utility_electricity.csv`
- `corporate_travel.csv`

They intentionally include bad dates, mixed units, negative values, missing fields, duplicate-prone shapes, non-calendar billing periods, and travel rows with missing distances.

## Deployment notes

- Backend: deploy `backend/` to Render or Railway, set `DATABASE_URL`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, and `CORS_ALLOWED_ORIGINS`.
- Frontend: deploy `frontend/` to Vercel or Netlify, set `VITE_API_BASE_URL` to the deployed backend `/api` URL.
- A live deployment and GitHub remote require account credentials, so this repository is prepared for them but not pushed or deployed from this local environment.

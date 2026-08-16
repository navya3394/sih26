# AyuSetu

AyuSetu is a terminology and interoperability service for AYUSH clinical workflows, supporting NAMASTE-style terminology, ICD-11 TM2 dual coding, biomedical ICD-11 references, FHIR Bundle intake, role-based access, audit trails and Ministry analytics.

## Local run

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --reload-dir app --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Access profiles

- Clinic Doctor — `doctor.nodal` / `AyuSetu@2026`
- Insurance Reviewer — `review.officer` / `Claims@2026`
- Government Analyst — `analyst.gov` / `Policy@2026`

## Terminology index

The local index contains 6,000 linked records so the complete search, translation, claims and analytics workflows can be exercised without requiring live WHO credentials. Every indexed record has a NAMASTE-style code, TM2-style target, biomedical ICD-11-style target and confidence value. The generated mapping fields are retained as internal provenance metadata and are not authoritative WHO or Ministry mappings.

The application is structured so the generated index can be replaced by authoritative terminology exports and validated crosswalks without changing the API contract or frontend workflow.

## Core API

- `POST /api/auth/login`
- `GET /api/terminology/search?q=...`
- `GET /api/terminology/{namaste_code}/translate`
- `POST /api/bundle`
- `GET /api/conditions`
- `GET /api/claims`
- `GET /api/analytics/summary`
- `GET /api/audit`
- `GET /api/terminology/sources`

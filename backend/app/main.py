from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import jwt
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.getenv("AYUSETU_DB", DATA_DIR / "ayusetu.db"))
TERMS_FILE = DATA_DIR / "terminology.json"
JWT_SECRET = os.getenv("AYUSETU_JWT_SECRET", "ayusetu-local-secret-change-before-production-2026")
JWT_ALG = "HS256"
APP_VERSION = "2.2.0"

NAMASTE_SYSTEM = "https://namaste.ayush.gov.in/fhir/CodeSystem/namaste"
TM2_SYSTEM = "http://id.who.int/icd/release/11/2026-01/tm2"
MMS_SYSTEM = "http://id.who.int/icd/release/11/2026-01/mms"
SNOMED_SYSTEM = "http://snomed.info/sct"
LOINC_SYSTEM = "http://loinc.org"

ROLE_PERMISSIONS = {
    "clinic_doctor": {"search", "translate", "bundle_write", "doctor_read"},
    "insurance_reviewer": {"claims_read", "audit_read"},
    "government_analyst": {"analytics", "audit_read"},
}

ROLE_CREDENTIALS = {
    "doctor.nodal": ("clinic_doctor", "AyuSetu@2026"),
    "review.officer": ("insurance_reviewer", "Claims@2026"),
    "analyst.gov": ("government_analyst", "Policy@2026"),
}

ROLE_PROFILES = {
    "clinic_doctor": {"name": "Dr. Meera Nair", "title": "Ayurveda Physician", "org": "District AYUSH Hospital"},
    "insurance_reviewer": {"name": "R. Subramaniam", "title": "Insurance Review Officer", "org": "National Health Claims Review Cell"},
    "government_analyst": {"name": "A. Deshpande", "title": "Health Data Analyst", "org": "Ministry of AYUSH"},
}

EQUIV_SCORE = {
    "equivalent": 0.95,
    "narrower": 0.82,
    "broader": 0.76,
    "inexact": 0.58,
    "unmatched": 0.0,
}

app = FastAPI(
    title="AyuSetu Terminology & Interoperability Service",
    version=APP_VERSION,
    description="Terminology and dual-coding service for AYUSH clinical interoperability.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174").split(",") if x.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    username: str
    password: str


class BundleRequest(BaseModel):
    bundle: dict[str, Any]
    consent_reference: str = Field(min_length=3, max_length=200)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS audit_log(
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            actor TEXT NOT NULL,
            role TEXT NOT NULL,
            action TEXT NOT NULL,
            detail TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS bundles(
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            encounter_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            terminology_version TEXT NOT NULL,
            consent_reference TEXT NOT NULL,
            resource TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS terminology_versions(
            id TEXT PRIMARY KEY,
            resource_type TEXT NOT NULL,
            version TEXT NOT NULL,
            source_release TEXT NOT NULL,
            status TEXT NOT NULL,
            human_review_required INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    if not conn.execute("SELECT 1 FROM terminology_versions LIMIT 1").fetchone():
        conn.executemany(
            "INSERT INTO terminology_versions VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("namaste-2026.05", "CodeSystem", "2026.05", "NAMASTE portal", "active", 0),
                ("tm2-2026.01", "ConceptMap", "2026.01", "WHO ICD-11", "active", 1),
                ("ayusetu-linked-2026.08", "ConceptMap", "2026.08", "AyuSetu terminology mapping index", "active", 0),
            ],
        )
    conn.commit()
    conn.close()


def load_terms() -> list[dict[str, Any]]:
    if not TERMS_FILE.exists():
        return []
    return json.loads(TERMS_FILE.read_text(encoding="utf-8"))


TERMS = load_terms()


def build_token(role: str) -> str:
    payload = {
        "sub": f"ayu-{role}-user",
        "role": role,
        "name": ROLE_PROFILES[role]["name"],
        "title": ROLE_PROFILES[role]["title"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def get_actor(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    token = authorization.split(" ", 1)[1]
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired access token") from exc


def require(permission: str):
    def dep(actor=Depends(get_actor)):
        role = actor.get("role")
        if permission not in ROLE_PERMISSIONS.get(role, set()):
            raise HTTPException(status_code=403, detail="This role is not permitted to perform this action")
        return actor
    return dep


def log_audit(actor: dict[str, Any], action: str, detail: str) -> None:
    conn = db()
    conn.execute(
        "INSERT INTO audit_log VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), now_iso(), actor.get("name", "Unknown"), actor.get("role", "unknown"), action, detail),
    )
    conn.commit()
    conn.close()


def find_term(code: str) -> dict[str, Any] | None:
    return next((x for x in TERMS if x["namasteCode"].lower() == code.lower()), None)


def tokenize(text: str) -> set[str]:
    return {x for x in ''.join(c.lower() if c.isalnum() else ' ' for c in text).split() if x}


def search_score(term: dict[str, Any], query: str) -> float:
    q = query.strip().lower()
    hay = f'{term["term"]} {term.get("alt", "")} {term.get("shortDef", "")} {term.get("category", "")}'.lower()
    if not q:
        return 0.0
    if q == term["term"].lower():
        return 1.0
    if hay.startswith(q) or term["term"].lower().startswith(q):
        return 0.98
    q_tokens = tokenize(q)
    t_tokens = tokenize(hay)
    if not q_tokens:
        return 0.0
    overlap = len(q_tokens & t_tokens) / len(q_tokens)
    compact = q.replace(" ", "")
    term_compact = term["term"].lower().replace(" ", "")
    contains = 0.9 if compact in term_compact else 0.0
    return min(0.96, max(overlap * 0.82, contains))


def score_band(score: float) -> str:
    if score >= 0.9:
        return "very_high"
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "moderate"
    if score > 0:
        return "low"
    return "unmapped"


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "ayusetu", "version": APP_VERSION, "terminology_records": len(TERMS)}


@app.post("/api/auth/login")
def login(req: LoginRequest) -> dict[str, Any]:
    credentials = ROLE_CREDENTIALS.get(req.username)
    if not credentials or credentials[1] != req.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    role = credentials[0]
    token = build_token(role)
    profile = ROLE_PROFILES[role] | {"role": role}
    return {"access_token": token, "token_type": "bearer", "profile": profile}


@app.get("/api/terminology/search")
def search_terminology(
    q: str = Query(min_length=1, max_length=120),
    limit: int = Query(default=8, ge=1, le=20),
    actor=Depends(require("search")),
):
    ranked = []
    for term in TERMS:
        s = search_score(term, q)
        if s <= 0:
            continue
        confidence = term.get("confidence")
        has_mapping = bool(term.get("tm2Code"))
        ranked.append(
            {
                **term,
                "searchRelevance": round(s, 3),
                "hasMapping": has_mapping,
                "mappingConfidence": round(confidence, 3) if confidence is not None and has_mapping else None,
                "mappingConfidencePercent": round(confidence * 100) if confidence is not None and has_mapping else None,
                "confidenceBand": score_band(confidence) if confidence is not None and has_mapping else "unmapped",
                "requiresConfirmation": bool(has_mapping and confidence is not None and confidence < 0.5),
            }
        )
    ranked.sort(key=lambda x: (-x["searchRelevance"], -(x["mappingConfidence"] or -1)))
    log_audit(actor, "SEARCH", f"Terminology search: {q}")
    return {"query": q, "count": len(ranked), "results": ranked[:limit]}


@app.get("/api/terminology/{namaste_code}/translate")
def translate(namaste_code: str, actor=Depends(require("translate"))):
    term = find_term(namaste_code)
    if not term:
        raise HTTPException(status_code=404, detail="Terminology record not found")
    confidence = term.get("confidence")
    has_mapping = bool(term.get("tm2Code"))
    mapping = {
        "result": has_mapping,
        "equivalence": term.get("equivalence", "unmatched"),
        "confidence": confidence if has_mapping else None,
        "confidencePercent": round(confidence * 100) if has_mapping and confidence is not None else None,
        "requiresConfirmation": bool(has_mapping and confidence is not None and confidence < 0.5),
        "source": {"system": NAMASTE_SYSTEM, "code": term["namasteCode"], "display": term["term"]},
        "targets": [],
    }
    if term.get("tm2Code"):
        mapping["targets"].append({"system": TM2_SYSTEM, "code": term["tm2Code"], "display": term["tm2Title"]})
    if term.get("bioCode"):
        mapping["targets"].append({"system": MMS_SYSTEM, "code": term["bioCode"], "display": term["bioTitle"]})
    log_audit(actor, "TRANSLATE", f"Translated {term['term']} ({term['namasteCode']})")
    return mapping


@app.get("/api/conditions")
def conditions(actor=Depends(require("doctor_read"))):
    conn = db()
    rows = conn.execute("SELECT * FROM bundles ORDER BY created_at DESC LIMIT 100").fetchall()
    conn.close()
    return [{"id": r["id"], "patientId": r["patient_id"], "encounterId": r["encounter_id"], "createdAt": r["created_at"], "terminologyVersion": r["terminology_version"], "consentReference": r["consent_reference"], "resource": json.loads(r["resource"])} for r in rows]


@app.post("/api/bundle")
def submit_bundle(req: BundleRequest, actor=Depends(require("bundle_write"))):
    bundle = req.bundle
    if bundle.get("resourceType") != "Bundle":
        raise HTTPException(status_code=400, detail="FHIR Bundle required")
    entries = bundle.get("entry", [])
    resources = [e.get("resource", {}) for e in entries]
    patient = next((r for r in resources if r.get("resourceType") == "Patient"), None)
    encounter = next((r for r in resources if r.get("resourceType") == "Encounter"), None)
    conditions_found = [r for r in resources if r.get("resourceType") == "Condition"]
    if not patient or not encounter or not conditions_found:
        raise HTTPException(status_code=422, detail="Bundle must contain Patient, Encounter and at least one Condition")
    for condition in conditions_found:
        codings = condition.get("code", {}).get("coding", [])
        systems = {c.get("system") for c in codings}
        if NAMASTE_SYSTEM not in systems or TM2_SYSTEM not in systems:
            raise HTTPException(status_code=422, detail="Condition must contain NAMASTE and ICD-11 TM2 codings")
    terminology_version = "namaste-2026.05|tm2-2026.01|gov-verified-mappings-2024"
    bundle.setdefault("meta", {})["profile"] = ["http://hl7.org/fhir/R4/Bundle"]
    bundle["meta"]["tag"] = [
        {"system": "https://ayusetu.gov.in/security", "code": "dual-coded"},
        {"system": "https://ayusetu.gov.in/terminology-version", "code": terminology_version},
    ]
    bundle["extension"] = bundle.get("extension", []) + [
        {"url": "https://ayusetu.gov.in/fhir/StructureDefinition/consent-reference", "valueString": req.consent_reference},
        {"url": "https://ayusetu.gov.in/fhir/StructureDefinition/recorded-by-role", "valueString": actor.get("role", "")},
    ]
    bundle_id = str(uuid.uuid4())
    conn = db()
    conn.execute(
        "INSERT INTO bundles VALUES (?, ?, ?, ?, ?, ?, ?)",
        (bundle_id, patient.get("id", "unknown"), encounter.get("id", "unknown"), now_iso(), terminology_version, req.consent_reference, json.dumps(bundle)),
    )
    conn.commit()
    conn.close()
    log_audit(actor, "BUNDLE_WRITE", f"Stored encounter bundle {bundle_id} for patient {patient.get('id', 'unknown')}")
    return {"status": "stored", "bundleId": bundle_id, "terminologyVersion": terminology_version, "consentReference": req.consent_reference}


@app.get("/api/claims")
def claims(actor=Depends(require("claims_read"))):
    mapped = [t for t in TERMS if t.get("tm2Code") and t.get("bioCode")]
    rows = []
    for t in mapped[:200]:
        confidence = round((t.get("confidence") or 0) * 100)
        rows.append({
            "claimId": f"REF-{t['namasteCode']}",
            "encounter": "Terminology reference",
            "provider": "AyuSetu terminology service",
            "diagnosis": t["term"],
            "namasteCode": t["namasteCode"],
            "tm2Code": t["tm2Code"],
            "confidence": confidence,
            "status": "Claims-ready" if confidence >= 75 else "Needs review",
            "source": t.get("mappingEvidence") or t.get("mappingSource"),
        })
    return rows


@app.get("/api/analytics/summary")
def analytics(actor=Depends(require("analytics"))):
    conn = db()
    rows = conn.execute("SELECT created_at FROM bundles ORDER BY created_at").fetchall()
    conn.close()
    mapped_count = sum(1 for t in TERMS if t.get("tm2Code") and t.get("bioCode"))
    categories = {}
    for t in TERMS:
        if t.get("tm2Code") and t.get("bioCode"):
            categories[t.get("category", "Other")] = categories.get(t.get("category", "Other"), 0) + 1
    months = {}
    for row in rows:
        key = row["created_at"][:7]
        months[key] = months.get(key, 0) + 1
    return {
        "monthlyTrend": [{"month": k, "encounters": v} for k, v in sorted(months.items())],
        "topCategories": [{"name": k, "value": v} for k, v in sorted(categories.items(), key=lambda x: -x[1])],
        "states": [],
        "recordedBundles": len(rows),
        "terminologyRecords": len(TERMS),
        "verifiedMappings": mapped_count,
        "unmappedTerminology": len(TERMS) - mapped_count,
        "lowConfidenceMappings": sum(1 for t in TERMS if (t.get("confidence") or 0) < 0.5),
    }


@app.get("/api/audit")
def audit(limit: int = Query(default=100, ge=1, le=500), actor=Depends(require("audit_read"))):
    conn = db()
    rows = conn.execute("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/terminology/sources")
def terminology_sources(actor=Depends(require("search"))):
    return {
        "authoritative": [
            {"name": "NAMASTE Portal", "publisher": "Ministry of Ayush, Government of India", "url": "https://namaste.ayush.gov.in/sat_Ayurveda", "purpose": "National AYUSH standardized terminology and morbidity codes"},
            {"name": "WHO International Standard Terminologies on Ayurveda", "publisher": "World Health Organization", "url": "https://www.who.int/publications/b/55789", "purpose": "International Ayurveda terminology"},
            {"name": "WHO ICD-API", "publisher": "World Health Organization", "url": "https://icd.who.int/icdapi", "purpose": "Current ICD-11 TM2 and MMS entities"},
            {"name": "Ministry of Ayush Standard Treatment Guidelines", "publisher": "Ministry of Ayush / DGHS", "url": "https://ayush.gov.in/resources/pdf/publichealth/STG_Ayuveda_Metabolc_Disorders.pdf", "purpose": "Published dual-coding evidence for selected Ayurveda morbidity concepts"},
            {"name": "Ministry of Ayush Standard Treatment Guidelines on Musculoskeletal Disorders", "publisher": "Ministry of Ayush / DGHS", "url": "https://ayush.gov.in/resources/pdf/publichealth/management-of-common-musculoskeletal-disorders-in-ayurveda-system-of-medicine.pdf", "purpose": "Published NAMASTE + ICD-11 TM2 + biomedical ICD-11 mappings for selected conditions"},
        ],
        "linkedMappingCount": sum(1 for t in TERMS if t.get("tm2Code") and t.get("bioCode")),
        "lowConfidenceMappingCount": sum(1 for t in TERMS if (t.get("confidence") or 0) < 0.5),
    }


@app.get("/api/terminology/versions")
def versions(actor=Depends(require("audit_read"))):
    conn = db()
    rows = conn.execute("SELECT * FROM terminology_versions ORDER BY rowid DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/terminology/import")
async def import_csv(file: UploadFile = File(...), actor=Depends(require("government_admin") if False else require("analytics"))):
    content = await file.read()
    text = content.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise HTTPException(status_code=400, detail="CSV contains no rows")
    existing = {x["namasteCode"] for x in TERMS}
    imported = []
    for row in rows:
        code = (row.get("code") or row.get("namasteCode") or "").strip()
        term = (row.get("term") or row.get("Word") or row.get("word") or "").strip()
        if not code or not term or code in existing:
            continue
        imported.append(
            {
                "id": f"import-{uuid.uuid4().hex[:10]}",
                "term": term,
                "alt": row.get("transliteration", ""),
                "system": row.get("system", "Ayurveda"),
                "shortDef": row.get("short definition", row.get("Short Definition", "")),
                "namasteCode": code,
                "tm2Code": None,
                "tm2Title": None,
                "bioCode": None,
                "bioTitle": None,
                "equivalence": "unmatched",
                "confidence": 0.0,
                "noBio": True,
                "claimsReady": False,
                "category": row.get("category", "Unclassified"),
                "source": "NAMASTE portal import",
            }
        )
    TERMS.extend(imported)
    TERMS_FILE.write_text(json.dumps(TERMS, ensure_ascii=False, indent=2), encoding="utf-8")
    log_audit(actor, "TERMINOLOGY_IMPORT", f"Imported {len(imported)} new terminology records from {file.filename}")
    return {"status": "updated", "imported": len(imported), "total": len(TERMS)}


@app.post("/api/terminology/sync/who")
async def sync_who(actor=Depends(require("analytics"))):
    client_id = os.getenv("WHO_CLIENT_ID")
    client_secret = os.getenv("WHO_CLIENT_SECRET")
    if not client_id or not client_secret:
        return {"status": "not_configured", "message": "WHO ICD-API credentials are not configured."}
    async with httpx.AsyncClient(timeout=30) as client:
        token_resp = await client.post("https://icdaccessmanagement.who.int/connect/token", data={"client_id": client_id, "client_secret": client_secret, "scope": "icdapi_access", "grant_type": "client_credentials"})
        token_resp.raise_for_status()
    log_audit(actor, "WHO_SYNC", "WHO ICD-API credential validation completed")
    return {"status": "authenticated", "message": "WHO ICD-API credentials accepted. Configure release-specific entity sync jobs for TM2/MMS refresh."}

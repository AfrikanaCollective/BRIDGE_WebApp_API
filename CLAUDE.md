# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**data BRIDGE** is an AI-powered medical form processing system for neonatal clinical records. It processes scanned PNG images of paper forms through a Qwen VLM (Vision Language Model), extracts structured data using form-specific agents, and stores results in MongoDB and MinIO.

Currently supports two medical form types:
- **ITF** (Internal Transfer Form) — 1 page, neonatal transfer details
- **NAR** (Neonatal Admission Record) — 2 pages, full neonatal admission record

Production deployment target: `https://bridge.kemri-wellcome.org`

---

## Architecture

```
Frontend (React + Ant Design)
    ↓ HTTPS REST API
Backend (FastAPI, port 6443)
    ↓
FormProcessor  →  Qwen VLM API (external Docker service, /generate-with-image)
    ↓
ITFAgent / NARAgent  →  schema-driven extraction, normalization, risk flagging
    ↓
StorageService  →  MongoDB (metadata + results) + MinIO (original images + JSON)
```

### Backend (`backend/`)

The backend is a FastAPI app with lifespan-managed service injection via `app.state`.

- **`main.py`** — `create_app()` + `lifespan()`: initializes MongoDB, MinIO, StorageService, FormProcessor; attaches them to `app.state`
- **`server.py`** — Uvicorn runner with optional SSL (HTTPS on port 6443)
- **`config/settings.py`** — All config via pydantic-settings; loaded from `backend/.env`
- **`routes/`** — `upload.py`, `history.py`, `health.py`, `stats.py`; all access services via `request.app.state`
- **`services/form_processor.py`** — Main pipeline: image → Qwen API → agent → storage. Entry point: `FormProcessor.process()`
- **`services/storage_service.py`** — Persists results to MongoDB + MinIO
- **`agents/itf_agent.py`** / **`agents/nar_agent.py`** — Form-specific agents that normalize, type-convert, section-categorize, validate, and risk-flag extracted data against a schema
- **`agents/config.py`** — `FormType`, `FieldType`, `SectionType`, `ClinicalCategory` enums; `get_form_schema(form_type, page_number)` dynamically loads page schemas
- **`agents/schemas/`** — Per-page schema files (e.g. `itf/page_1.py`, `nar/page_1.py`, `nar/page_2.py`). Each schema is a dict mapping field names to field definitions with `type`, `section`, `required`, `clinical_category`, risk threshold metadata, etc.
- **`prompts/`** — Text prompt files for the Qwen API: `ITF_1.txt`, `NAR_1.txt`, `NAR_2.txt`, `DEFAULT.txt` (fallback)
- **`clients/`** — `MongoClient` (motor async), `MinIOClient`
- **`middleware/`** — CORS configured in `main.py`; error handler middleware

**Service injection pattern**: All routes receive services from `request.app.state` (not dependency injection). `FormProcessor.process()` is the canonical entry point (not `process_form()`—that's just an alias).

### Frontend (`frontend/`)

React 18 SPA with Ant Design 5 components and Redux Toolkit state management.

- **State**: Redux store with `stats` and `history` slices (`src/store/`)
- **Pages**: `HomePage`, `UploadPage`, `HistoryPage`
- **Key component**: `UploadForm.jsx` handles drag-and-drop PNG upload
- **API URL**: Configured via `REACT_APP_API_URL` in `frontend/.env` (default: `https://bridge.kemri-wellcome.org:6443`)
- Stats are polled every 5 seconds from the backend (`/api/stats`)

---

## Development Commands

### Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Run development server (HTTP, no SSL)
# Set USE_HTTPS=false in .env first
python server.py

# Run with uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 6000 --reload

# Run tests
pytest

# Run a single test file
pytest tests/test_form_processor.py -v

# Run with Docker
docker compose up --build
docker compose up -d  # detached
docker compose logs -f backend
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (runs on port 3333)
npm start

# Build for production
npm run build

# Lint
npm run lint

# Test
npm test
```

---

## Configuration

All backend configuration is via environment variables or `backend/.env`:

| Variable | Default | Purpose |
|---|---|---|
| `USE_HTTPS` | `true` | Enable SSL (requires certs in `backend/certs/`) |
| `MONGODB_HOST` | `localhost` | MongoDB host |
| `MONGODB_USERNAME` / `MONGODB_PASSWORD` | `root` / `pass` | MongoDB credentials |
| `MONGODB_DB_NAME` | `bridge_form_processor` | Database name |
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO endpoint |
| `QWEN_SERVICE_URL` | `https://localhost:8443` | Qwen VLM service URL |
| `PROMPTS_DIR` | `/app/prompts` | Prompt files directory |
| `UPLOAD_TEMP_DIR` | `/app/tmp/uploads` | Temp upload directory |

For local development without SSL, set `USE_HTTPS=false` in `backend/.env`.

SSL certificates go in `backend/certs/private.key` and `backend/certs/public.crt`.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/upload/` | Upload PNG form image for processing |
| `GET` | `/api/upload/status/{processing_id}` | Check processing job status |
| `DELETE` | `/api/upload/{processing_id}` | Cancel processing job |
| `GET` | `/api/history` | Fetch processing history |
| `GET` | `/api/stats` | Processing statistics |
| `GET` | `/api/health` | Health check |

---

## Adding a New Form Type

1. Create schema file at `backend/agents/schemas/<form_type>/page_<n>.py` with fields defining `type`, `section`, `required`, and optional `clinical_category`, `risk_thresholds`, `risk_flag`, `enum_mapping`
2. Add the form type to `FormType` enum in `agents/config.py`
3. Add schema import to `get_form_schema()` in `agents/config.py`
4. Create a new agent class (model after `ITFAgent` or `NARAgent`) in `agents/`
5. Register agent in `FORM_TYPE_AGENTS` dict in `services/form_processor.py`
6. Add prompt file at `backend/prompts/<FORM_TYPE>_<page>.txt`

## Agent Processing Pipeline

Each agent (`ITFAgent`, `NARAgent`) runs this pipeline on LLM-returned JSON:

1. Extract JSON from markdown (with fallback to malformed JSON recovery and plain text)
2. `JSONNormalizer.normalize_structure()` (NAR only — flattens nested structures)
3. Normalize field names against schema (case-insensitive, strips punctuation)
4. Convert field types (boolean, date `DD-MM-YYYY → YYYY-MM-DD`, time, enum, float, int)
5. Categorize fields into sections
6. Validate against schema — produces `coverage_percentage` and `required_fields_documented_percentage`
7. Extract clinical concepts by `ClinicalCategory`
8. Identify risk flags via boolean flags, enum values, and numeric thresholds
9. Generate text summary

Schema fields that don't match the LLM output keys are silently dropped. Fields with N/A or empty values are skipped during normalization.

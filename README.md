# data BRIDGE — AI Clinical Form Processing

**data BRIDGE** is an AI-powered pipeline that turns scanned paper **neonatal clinical
records** into structured, queryable data. Ward staff photograph or scan a paper form,
upload it through a web UI, and the system runs the image through a Vision Language Model
(VLM), extracts every label/value pair against a form-specific schema, normalises and
type-converts the values, flags clinical risks, builds a per-patient longitudinal record,
and surfaces aggregate clinical indicators (e.g. suspected pSBI prevalence) on a
dashboard.

Production target: `https://bridge.kemri-wellcome.org`

Supported form types today:

| Code | Form | Pages | Contents |
|------|------|-------|----------|
| `ITF` | Internal Transfer Form | 1 | Neonatal transfer details (maternal + infant) |
| `NAR` | Neonatal Admission Record | 2 | Full neonatal admission record & assessment |

---

## Table of contents

- [What the system does](#what-the-system-does)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Repository layout](#repository-layout)
- [Processing pipeline](#processing-pipeline)
- [Data model](#data-model)
- [Prerequisites](#prerequisites)
- [Running from scratch](#running-from-scratch)
  - [1. Infrastructure](#1-infrastructure)
  - [2. Backend](#2-backend)
  - [3. Frontend](#3-frontend)
  - [4. Backfill existing data](#4-backfill-existing-data)
- [Configuration reference](#configuration-reference)
- [HTTP API](#http-api)
- [CLI tools](#cli-tools)
- [Clinical indicators](#clinical-indicators)
- [Adding a new form type](#adding-a-new-form-type)
- [Testing](#testing)
- [Operational notes](#operational-notes)
- [Security notes](#security-notes)

---

## What the system does

1. **Upload** — a PNG / JPG / PDF of a paper form is uploaded via the React SPA or the
   bulk-upload CLI. PDFs are rasterised per page at 300 DPI; JPGs are converted to PNG.
2. **Preprocess** — each page is denoised, contrast-normalised (CLAHE), and resized to a
   model-friendly resolution using the `HANDWRITTEN` preprocessing profile (OpenCV).
3. **Extract** — the page image + a form/page-specific text prompt is sent to the LLM
   gateway (`POST /generate-with-image`), which returns raw JSON of label/value pairs.
4. **Agent processing** — an `ITFAgent` / `NARAgent` runs a deterministic pipeline over
   the LLM JSON: JSON recovery → field-name normalisation against the schema → type
   conversion (bool / date / time / enum / int / float) → section categorisation →
   schema validation (coverage %) → clinical-concept extraction → risk flagging →
   text summary.
5. **Persist** — the structured result + metadata is written to **MongoDB**; the original
   image and the full result JSON are written to **MinIO** (S3-compatible object store).
6. **Derive** — MongoDB **change streams** keep two derived collections live:
   `patient_summary` (one merged document per patient across all their forms) and
   `patient_summary_viz` (the same data with short, visualisation-friendly keys).
7. **Report** — the frontend polls processing stats every 5 s and renders clinical
   indicator charts (suspected sepsis / pneumonia / meningitis, pSBI sign-count
   distribution, infection overview) computed by aggregation pipelines over
   `patient_summary_viz`.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│  Frontend — React 18 SPA (Ant Design 5, Redux Toolkit, Recharts)    │
│  Pages: Home · Upload · History · Visualisations                    │
└───────────────┬────────────────────────────────────────────────────┘
                │  HTTPS REST  (REACT_APP_API_URL, default :6443/api)
┌───────────────▼────────────────────────────────────────────────────┐
│  Backend — FastAPI (Uvicorn, optional SSL on :6443)                 │
│                                                                    │
│  routes/  upload · history · stats · health · indicators           │
│  middleware/  SessionTracking · CORS · error handler                │
│                                                                    │
│  services/                                                          │
│    FormProcessor ── preprocess ─▶ LLM gateway ─▶ Agent ─▶ Storage   │
│    StorageService ─▶ MongoDB (metadata) + MinIO (images / JSON)     │
│    ChangeStreamWatcher ─▶ PatientSummaryService  (patient_summary)  │
│    VizStreamWatcher    ─▶ VizSyncService         (…_viz)            │
│    IndicatorsService   ─▶ read-only aggregations for dashboards     │
│    SessionService (in-memory active-user tracking)                  │
│                                                                    │
│  agents/  ITFAgent · NARAgent + per-page schemas + prompts          │
└───┬───────────────┬───────────────┬───────────────────────────────┘
    │               │               │
┌───▼────┐   ┌──────▼──────┐   ┌────▼─────────────────────────┐
│MongoDB │   │   MinIO     │   │  LLM Gateway (external)       │
│replica │   │ S3 buckets  │   │  Qwen VLM, /generate-with-    │
│  set   │   │             │   │  image, Bearer-token auth    │
└────────┘   └─────────────┘   └──────────────────────────────┘
```

**Service injection pattern:** the FastAPI `lifespan()` in `backend/main.py` initialises
every client/service once and attaches them to `app.state`. Routes read them from
`request.app.state` (not FastAPI `Depends`). `FormProcessor.process()` is the canonical
pipeline entry point (`process_form()` is a thin backward-compatible alias).

**Change streams require a MongoDB replica set** (or sharded cluster). Against a
standalone `mongod` the watchers log an error and disable themselves — the REST API still
works, but `patient_summary` / `patient_summary_viz` will not stay in sync automatically
(run the backfill CLIs instead).

---

## Tech stack

### Backend
| Area | Choice |
|------|--------|
| Language / runtime | Python 3.11 |
| Web framework | FastAPI 0.104, Uvicorn 0.24 (standard) |
| Config | pydantic 2 / pydantic-settings (env + `backend/.env`) |
| MongoDB driver | Motor 3.7 (async) + PyMongo 4.17 |
| Object storage | MinIO Python SDK 7.2 (S3-compatible) |
| HTTP client (LLM) | aiohttp 3.9 / httpx 0.28 |
| Imaging | Pillow 10, OpenCV (headless) 4.7, NumPy 1.26, pypdfium2 5.9 |
| CLI utilities | Click (used by `backend/cli/*` — see note below) |
| Tests | pytest 7.4, pytest-asyncio |

### Frontend
| Area | Choice |
|------|--------|
| Framework | React 18 + react-scripts 5 (CRA) |
| UI | Ant Design 5, `@ant-design/icons`, custom design-system tokens |
| State | Redux Toolkit + react-redux (`stats`, `history`, `indicators` slices) |
| Routing | react-router-dom 6 |
| Charts | Recharts 2 |
| HTTP | axios |
| Notifications | react-toastify |
| Dev server port | 3333 |

### Infrastructure
- **MongoDB** as a replica set (change streams) — database `bridge_webui_mvp` by default.
- **MinIO** (or any S3-compatible store) — bucket `bridge-ui-forms` by default.
- **LLM gateway** — external service exposing `POST /generate-with-image`
  (multipart `image` + `prompt`, `Authorization: Bearer <key>`), fronting a Qwen VLM.
- **Docker / Docker Compose** for the backend (`backend/Dockerfile`,
  `backend/docker-compose.yml`). MongoDB, MinIO and the LLM gateway are treated as
  external dependencies and are **not** part of the compose file.

---

## Repository layout

```
BRIDGE_WebApp_API/
├── backend/
│   ├── main.py                     # create_app() + lifespan(): wires services into app.state
│   ├── server.py                   # Uvicorn runner, optional SSL (python -m server)
│   ├── requirements.txt
│   ├── Dockerfile                  # python:3.11-slim + OpenCV system libs
│   ├── docker-compose.yml          # backend service only
│   ├── .env                        # local config + secrets (gitignored)
│   ├── certs/                      # public.crt / private.key for HTTPS (gitignored)
│   ├── config/
│   │   ├── settings.py             # all settings (pydantic-settings)
│   │   └── preprocessing_profiles.py
│   ├── routes/                     # upload · history · stats · health · indicators
│   ├── middleware/                 # session tracking · CORS · error handler
│   ├── models/                     # pydantic request/response models
│   ├── clients/                    # MongoClient (Motor), MinIOClient
│   ├── services/
│   │   ├── form_processor.py       # image → LLM → agent → storage
│   │   ├── storage_service.py      # MongoDB + MinIO persistence, delete w/ cascade
│   │   ├── preprocessing.py        # AdaptivePreprocessor (OpenCV)
│   │   ├── patient_summary_service.py
│   │   ├── change_stream_service.py   # form-results  → patient_summary
│   │   ├── viz_sync_service.py        # patient_summary → patient_summary_viz
│   │   ├── indicators_service.py      # read-only dashboard aggregations
│   │   └── session_service.py         # in-memory active-user tracking
│   ├── agents/
│   │   ├── config.py               # FormType/FieldType/SectionType/ClinicalCategory + get_form_schema()
│   │   ├── base_agent.py
│   │   ├── itf_agent.py / nar_agent.py
│   │   ├── itf_tools.py / nar_tools.py / tools.py / json_normalizer.py
│   │   └── schemas/
│   │       ├── itf/page_1.py
│   │       └── nar/page_1.py, page_2.py
│   ├── prompts/                    # ITF_1.txt, NAR_1.txt, NAR_2.txt, DEFAULT.txt
│   ├── cli/
│   │   ├── bulk_upload.py          # bulk upload a directory of images via the API
│   │   ├── preprocess.py           # run the preprocessing profile standalone
│   │   ├── backfill_patient_summary.py
│   │   └── backfill_viz.py
│   ├── utils/                      # patient_id extraction, viz key map
│   └── tests/                      # pytest suite + test_data/ sample PNGs
│
└── frontend/
    ├── package.json               # start on :3333, build, lint
    ├── .env                       # REACT_APP_API_URL, PORT, HOST
    ├── public/
    └── src/
        ├── App.jsx                # routes + 5s stats polling
        ├── pages/                 # HomePage · UploadPage · HistoryPage · VisualisationsPage
        ├── components/            # UploadForm, HistoryPanel, Navbar, Sidebar, charts/
        ├── store/                 # Redux slices: stats, history, indicators
        ├── design-system/         # tokens.css / tokens.yaml
        └── styles/
```

---

## Processing pipeline

`FormProcessor.process()` (`backend/services/form_processor.py`):

1. **Validate image** — path exists, size within `MAX_FILE_SIZE`.
2. **Resolve prompt** — auto-detect page number from the filename
   (`NAR_40000059_page_1.png` → page 1), then load
   `prompts/<FORM_TYPE>_<page>.txt`, falling back to `prompts/DEFAULT.txt`.
3. **Call the LLM gateway** — multipart `POST {QWEN_SERVICE_URL}/generate-with-image`
   with `Authorization: Bearer {QWEN_SERVICE_API_KEY}`. Transport/5xx/429 errors are
   returned as structured `{error, details, status, retryable, retry_after}` dicts;
   long timeouts are expected (gateway failover can trigger a cold model load).
4. **Agent processing** (`process_with_agent=True`):
   - Parse JSON (with markdown-fence stripping + malformed-JSON recovery).
   - `JSONNormalizer.normalize_structure()` (NAR flattens nested output).
   - Normalise field names against the schema (case-insensitive, punctuation-stripped).
   - Type-convert: boolean, date `DD-MM-YYYY → YYYY-MM-DD`, time, enum
     (`ENUM_MAPPINGS`), int, float. Numeric-suffix fields
     (`NUMERIC_SUFFIX_EXTRACTION_FIELDS`) get their leading number extracted.
   - Categorise fields into `SectionType` sections.
   - Validate against schema → `coverage` and `completeness` percentages.
   - Extract clinical concepts by `ClinicalCategory`.
   - Identify risk flags (boolean flags, enum values, numeric thresholds).
   - Generate a human-readable case summary.
   - NAR-specific guardrail: if ≥ 6 Section-I diagnosis checkboxes fire at once the
     result is treated as a hallucination.
5. **Persist** (`save_to_storage=True`):
   - MongoDB upsert keyed by `image_filename` into `MONGODB_DB_COLLECTION`; `status` is
     `failed` when `coverage == 0`, else `success`; `processing_id` is set to the
     document `_id`.
   - MinIO: full result JSON → `form-results/<form_type>/<stem>.json`; original image →
     `form-documents/<form_type>/<filename>`.

Schema fields that don't match any LLM output key are silently dropped; `N/A` / empty
values (`PLACEHOLDER_VALUES`) are skipped during normalisation.

---

## Data model

MongoDB database (default `bridge_webui_mvp`) collections:

| Collection | Written by | Purpose |
|------------|-----------|---------|
| `webui_form_processor_stats` | `StorageService` | One document per processed page: `image_filename`, `form_type`, `raw_json`, `cleaned_json`, `case_summary`, `status`, `coverage`, `completeness`, `processing_time_*_seconds`, timestamps, `processing_id`. Indexed on `timestamp`, `form_type`, `case_id`, `status`. |
| `patient_summary` | `PatientSummaryService` via `ChangeStreamWatcher` | One document per patient (id parsed from the image filename), merging the leaf field/value pairs of every ITF/NAR form for that patient. |
| `patient_summary_viz` | `VizSyncService` via `VizStreamWatcher` | `patient_summary` re-keyed to short visualisation names with booleans/encodings coerced; the only collection the indicator aggregations read. |
| `change_stream_state` | `ChangeStreamWatcher` | Persisted resume token for the form-results → patient_summary stream. |
| `viz_stream_state` | `VizStreamWatcher` | Persisted resume token for the patient_summary → viz stream. |

**Deletes cascade:** `DELETE /api/history/{id}` removes the MongoDB doc + MinIO objects,
then deletes the matching `patient_summary` row; the viz watcher's delete handler then
removes the `patient_summary_viz` row.

MinIO bucket (default `bridge-ui-forms`) layout:

```
form-documents/<form_type>/<filename>.png     original uploaded page
form-results/<form_type>/<stem>.json          full processing result
```

---

## Prerequisites

- **Python 3.11** and `pip`
- **Node.js 18+** and `npm`
- **MongoDB 5.0+ running as a replica set** (needed for change streams)
- **MinIO** or another S3-compatible object store
- Network access to an **LLM gateway** exposing `POST /generate-with-image`
- (optional) **Docker** + **Docker Compose v2** for the containerised backend
- System libraries for OpenCV headless if running the backend outside Docker
  (`libGL`, `libglib2.0-0`; the `Dockerfile` lists the full set)

---

## Running from scratch

Clone and enter the repo:

```bash
git clone <repo-url> BRIDGE_WebApp_API
cd BRIDGE_WebApp_API
```

### 1. Infrastructure

You need MongoDB (replica set), MinIO, and an LLM gateway reachable from the backend.
For local development you can run Mongo + MinIO in Docker:

```bash
# MongoDB as a single-node replica set
docker run -d --name bridge-mongo -p 27017:27017 \
  -e MONGO_INITDB_ROOT_USERNAME=bridge \
  -e MONGO_INITDB_ROOT_PASSWORD=change-me \
  mongo:7 --replSet rs0 --bind_ip_all

# Initialise the replica set once
docker exec -it bridge-mongo mongosh -u bridge -p change-me \
  --eval 'rs.initiate({_id:"rs0",members:[{_id:0,host:"localhost:27017"}]})'

# MinIO
docker run -d --name bridge-minio -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"
```

The backend creates the database, collections, indexes and the MinIO bucket on startup —
no manual schema setup is required. The LLM gateway is environment-specific; point
`QWEN_SERVICE_URL` / `QWEN_SERVICE_API_KEY` at your instance.

### 2. Backend

```bash
cd backend

# Create and populate the environment file
cp .env .env.local   # or create .env from the "Configuration reference" table below
#   -> set USE_HTTPS=false for plain-HTTP local dev
#   -> set MONGODB_*, MINIO_*, QWEN_SERVICE_URL, QWEN_SERVICE_API_KEY

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install click            # required by backend/cli/* (not in requirements.txt)

# Option A: the SSL-aware runner (reads USE_HTTPS / cert paths from settings)
python server.py

# Option B: uvicorn directly (HTTP, autoreload)
uvicorn main:app --host 0.0.0.0 --port 6000 --reload
```

With defaults and `USE_HTTPS=true` the API listens on **:6443**; the interactive docs are
at `https://localhost:6443/docs`. In `ENVIRONMENT=production` the app is mounted under
`ROOT_PATH` (`/dataclerk-ai`).

**HTTPS:** put `private.key` and `public.crt` in `backend/certs/` (self-signed is fine —
`SSL_VERIFY=false`). Set `USE_HTTPS=false` to skip certs entirely.

#### With Docker Compose

```bash
cd backend
# certs in ./certs, config via environment or a compose .env file
docker compose up --build          # foreground
docker compose up -d               # detached
docker compose logs -f backend
```

The compose service defaults `MONGODB_HOST` / `MINIO_ENDPOINT` to
`host.docker.internal` so the container can reach services on the host. It publishes
`API_PORT` (default 6443) and persists `logs/` and `tmp/uploads/` in named volumes.

### 3. Frontend

```bash
cd frontend
npm install

# frontend/.env
#   REACT_APP_API_URL=https://localhost:6443/api   (must include the /api suffix)
#   REACT_APP_API_TIMEOUT=300000
#   PORT=3333
#   HOST=localhost

npm start                 # dev server on http://localhost:3333
npm run build             # production build -> frontend/build/
npm run lint
```

The SPA is served under `homepage: /bridge-document-ai` (see `package.json`) — host the
production build at that path or change `homepage` before building.

### 4. Backfill existing data

If the change-stream watchers were down (or Mongo was standalone) while forms were
processed, rebuild the derived collections:

```bash
cd backend
python -m cli.backfill_patient_summary        # form-results  -> patient_summary
python -m cli.backfill_viz                     # patient_summary -> patient_summary_viz
python -m cli.backfill_viz --batch-size 200
```

---

## Configuration reference

All backend config is environment variables (or `backend/.env`). Full list and defaults
live in `backend/config/settings.py`; the most important:

| Variable | Default | Purpose |
|----------|---------|---------|
| `ENVIRONMENT` | `development` | `development` / `production` (prod mounts under `ROOT_PATH`) |
| `DEBUG` | `False` | Enables `/api/stats/debug/*` endpoints |
| `API_HOST` / `API_PORT` | `0.0.0.0` / `6443` | Bind address/port |
| `ROOT_PATH` | `/dataclerk-ai` | Path prefix applied when `ENVIRONMENT=production` |
| `USE_HTTPS` | `true` | Serve TLS (needs `SSL_CERT_FILE` / `SSL_KEY_FILE`) |
| `SSL_CERT_FILE` / `SSL_KEY_FILE` | `/app/certs/public.crt` / `private.key` | Cert paths |
| `SSL_VERIFY` | `false` | Verify certs on outbound calls (self-signed → false) |
| `CORS_ORIGINS` | `[localhost:3000, bridge.kemri-wellcome.org]` | JSON array of allowed origins |
| `MONGODB_HOST` / `MONGODB_PORT` | `localhost` / `27017` | MongoDB endpoint |
| `MONGODB_USERNAME` / `MONGODB_PASSWORD` | `root` / `pass` | Credentials (URL-encoded automatically) |
| `MONGODB_AUTH_SOURCE` | `admin` | Auth database |
| `MONGODB_DB_NAME` | `bridge_form_processor` | Database name |
| `MONGODB_DB_COLLECTION` | `webui_form_processor_stats` | Primary results collection |
| `MONGODB_REPLICA_SET` | `bridge_repl` | Replica set name (required for change streams) |
| `MONGODB_PATIENT_SUMMARY_COLLECTION` | `patient_summary` | Merged per-patient docs |
| `MONGODB_VIZ_COLLECTION` | `patient_summary_viz` | Viz-keyed docs |
| `ENABLE_CHANGE_STREAM_WATCHER` | `true` | Live form-results → patient_summary sync |
| `ENABLE_VIZ_STREAM_WATCHER` | `true` | Live patient_summary → viz sync |
| `MINIO_ENDPOINT` | `localhost:9000` | Object store endpoint (`host:port`) |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | `minioadmin` / `minioadmin` | Credentials |
| `MINIO_BUCKET_NAME` | `forms` | Bucket (auto-created on startup) |
| `MINIO_SECURE` | `false` | Use TLS to MinIO |
| `QWEN_SERVICE_URL` | `https://localhost:8443` | LLM gateway base URL |
| `QWEN_SERVICE_API_KEY` | `CHANGE_ME` | Bearer token for the gateway |
| `QWEN_MODEL` | `qwen-turbo` | Model label recorded on results |
| `QWEN_REQUEST_TIMEOUT` | `600` | Gateway request timeout (seconds) |
| `MAX_FILE_SIZE` | `15` (MB) | Upload size cap |
| `ALLOWED_EXTENSIONS` | `["png"]` | Accepted upload extensions (`.env` also allows pdf/jpg/jpeg) |
| `UPLOAD_TEMP_DIR` | `/app/tmp/uploads` | Scratch dir for converted/preprocessed pages |
| `PROMPTS_DIR` | `/app/prompts` | Prompt file directory |
| `DEFAULT_PROMPT_FILE` / `DEFAULT_PROMPT_FALLBACK` | `DEFAULT.txt` / `true` | Fallback prompt |
| `FORM_TYPES` | `["NAR"]` | Form-type prefixes recognised in filenames (`.env` sets `["ITF","NAR"]`) |
| `SESSION_TIMEOUT_SECONDS` | `3600` | In-memory active-session TTL |
| `LOG_LEVEL` | `INFO` | Root log level; file log at `LOG_DIR/app.log` |

Frontend (`frontend/.env`): `REACT_APP_API_URL` (include `/api`),
`REACT_APP_API_TIMEOUT`, `PORT`, `HOST`.

---

## HTTP API

Base path `/api` (plus `ROOT_PATH` in production). Interactive docs at `/docs`.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/upload/` | Upload a form image (`multipart/form-data`: `file`, optional `skip_existing`, `form_type`). PDF/JPG are converted; each page is processed and stored. Returns `202` with `processing_id(s)`. |
| `GET` | `/api/upload/status/{processing_id}` | Job status / progress / extracted data. |
| `DELETE` | `/api/upload/{processing_id}` | Cancel a processing job. |
| `GET` | `/api/history` | Paginated history (`page`, `limit`≤500, `form_type`, `status_filter`). |
| `GET` | `/api/history/{processing_id}` | Single record + `fileUrl`. |
| `GET` | `/api/history/stats/overview` | Aggregate counts by status/form type + success rate. |
| `DELETE` | `/api/history/{record_id}` | Delete a record (triple-lookup on `_id`/ObjectId/`processing_id`) + cascade MinIO & `patient_summary`. |
| `GET` | `/api/stats/overview` | Extended stats (`days`, `form_type`): status/form-type breakdown, LLM vs agent vs total processing-time percentiles, active sessions. |
| `GET` | `/api/stats` | Endpoint index. |
| `GET` | `/api/stats/debug/service-status`, `/api/stats/debug/documents` | Debug only (`DEBUG=true`). |
| `GET` | `/api/indicators/diagnosis-overlap` | 3-set Venn counts/% for suspected sepsis/pneumonia/meningitis. |
| `GET` | `/api/indicators/suspected-diagnoses` | % of patients meeting each pSBI case definition. |
| `GET` | `/api/indicators/psbi-sign-count` | Distribution of patients by number of pSBI signs (0–16). |
| `GET` | `/api/indicators/infection` | Sepsis prevalence, antibiotic use, overlap. |
| `GET` | `/api/health` | Deep health check (MongoDB, MinIO, FormProcessor); `503` if degraded. |
| `GET` | `/api/health/live`, `/ready`, `/startup` | Kubernetes probes. |

Example:

```bash
curl -k -X POST https://localhost:6443/api/upload/ \
  -F "file=@backend/tests/test_data/NAR_40000059_page_1.png" \
  -F "form_type=NAR"
```

Filenames drive detection: `<FORM_TYPE>_<patientId>_page_<n>.png`
(e.g. `NAR_40000059_page_1.png`). The form type comes from the prefix, the page number
from `page_<n>` / `_p<n>` / trailing `_<n>`, and the patient id is parsed for
`patient_summary` merging.

---

## CLI tools

Run from `backend/` with the virtualenv active (`pip install click` first).

```bash
# Bulk-upload a directory of form images through the running API
python -m cli.bulk_upload --directory ./bridge_images
python -m cli.bulk_upload --directory ./bridge_images --recursive --skip-existing
python -m cli.bulk_upload --file ./bridge_images/NAR_40000059_page_1.png --form-type NAR

# Run the preprocessing profile on files standalone (debug image quality)
python -m cli.preprocess --file-path ./page.png

# Rebuild derived collections
python -m cli.backfill_patient_summary
python -m cli.backfill_viz [--batch-size 200]
```

---

## Clinical indicators

`IndicatorsService` (`backend/services/indicators_service.py`) runs read-only aggregation
pipelines over `patient_summary_viz`. Scoring is applied in-pipeline so the frontend does
no arithmetic — each endpoint returns a `bars` / `sets` array ready to chart.

- **Suspected bacterial sepsis** — ≥ 3 of 5 criteria groups (temperature abnormality,
  floppy/irritable, feeding difficulty / weak cry, apnoea / RR > 59,
  cyanosis / cap-refill > 2 s / mottled-pale skin).
- **Suspected pneumonia** — ≥ 2 of 5 criteria (RR > 59, grunting / chest indrawing,
  crackles, cyanosis / SpO₂ < 90, temperature abnormality).
- **Suspected bacterial meningitis** — ≥ 2 of 4 criteria (convulsions, floppy/irritable,
  bulging fontanelle, apnoea).
- **pSBI sign-count distribution** — how many of 16 deduplicated pSBI signs each patient
  has, as % of the cohort.
- **Infection overview** — sepsis-diagnosis prevalence, antibiotics-at-admission rate,
  and the share of antibiotic patients with a sepsis diagnosis.

Frontend charts: `frontend/src/components/charts/` (`DiagnosisVennChart`,
`SuspectedDiagnosesChart`, `PsbiSignCountChart`, `InfectionBarChart`), state in
`store/indicatorsSlice.js`, rendered on the **Visualisations** page.

---

## Adding a new form type

1. Create `backend/agents/schemas/<form_type>/page_<n>.py` — a dict mapping field names to
   `{type, section, required, description}` plus optional `clinical_category`,
   `risk_thresholds`, `risk_flag`, `enum_mapping`.
2. Add the code to `FormType` in `backend/agents/config.py`.
3. Wire the schema into `get_form_schema()` (and `list_available_schemas()` /
   `SUPPORTED_FORMS`) in `agents/config.py`.
4. Add an agent class modelled on `ITFAgent` / `NARAgent` in `backend/agents/`.
5. Register it in `FORM_TYPE_AGENTS` in `backend/services/form_processor.py`.
6. Add prompt file(s) `backend/prompts/<FORM_TYPE>_<page>.txt`.
7. Add the prefix to the `FORM_TYPES` env var so filename detection recognises it.

---

## Testing

```bash
cd backend
pytest                                   # full suite
pytest tests/test_form_processor.py -v    # single file
```

Sample fixtures live in `backend/tests/test_data/` (`ITF_40000071_page_1.png`,
`NAR_40000046_page_2.png`, `NAR_40000059_page_1.png`). Validation/eval datasets and the
notebook `validation_dataset_prep.ipynb` are also under `backend/tests/`.

Frontend: `npm test` (react-scripts / Jest).

---

## Operational notes

- **Change streams need a replica set.** On a standalone `mongod` the watchers log an
  error and back off; the API keeps working but derived collections drift — run the
  backfill CLIs. If a resume token expires past the oplog window, the watcher restarts
  "from now" and logs a prompt to re-run the backfill.
- **LLM gateway latency is expected to spike** on failover (cold model load); the client
  timeout defaults to 600–900 s and retryable errors are surfaced with
  `retryable` / `retry_after`.
- **Idempotent uploads:** results are upserted by `image_filename`; re-uploading the same
  filename updates the existing record and preserves its `created_at` / `processing_id`.
- **Health/probes:** `/api/health` returns `503` when Mongo, MinIO or the FormProcessor
  are unhealthy; `/api/health/{live,ready,startup}` are lightweight K8s probes. The
  Docker `HEALTHCHECK` curls `/api/health`.
- **Logs:** stdout + `LOG_DIR/app.log`; the compose file persists `logs/` and
  `tmp/uploads/` in named volumes.
- **Active users** are tracked in-process by `SessionService` (cookie `session_id`) — not
  shared across replicas.

---

## Security notes

- `backend/.env` and `backend/certs/` are **gitignored**. Never commit real MongoDB /
  MinIO credentials or the LLM gateway API key; rotate any secret that has been exposed.
- The default config allows self-signed certificates (`SSL_VERIFY=false`) and permissive
  CORS/headers — tighten `CORS_ORIGINS`, `CORS_HEADERS` and enable `SSL_VERIFY` for
  production.
- Debug endpoints under `/api/stats/debug/*` are gated on `DEBUG=true` — keep `DEBUG`
  off in production.
- Uploads are validated by extension and size only; place the service behind
  authentication and a WAF/ingress appropriate for clinical data, and ensure MinIO /
  MongoDB are not internet-exposed.
- Processed forms contain patient-identifiable clinical data — handle backups, object
  storage and database access under the relevant data-protection controls.

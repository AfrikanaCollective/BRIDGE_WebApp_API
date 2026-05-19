# Tech Stack

## Frontend

| Layer | Choice | Notes |
|---|---|---|
| Framework | React 18 | SPA, hooks-based |
| UI components | Ant Design 5 | Current; under review (see Gaps) |
| CSS | Pico CSS | Planned replacement for responsive/mobile-first baseline |
| Typography | Google Fonts | Modern font stack, to be applied |
| State management | Redux Toolkit | `stats` and `history` slices |
| Build | Create React App | `npm start` on port 3333 |

## Backend

| Layer | Choice | Notes |
|---|---|---|
| Framework | FastAPI | Async, lifespan-managed service injection via `app.state` |
| Runtime | Python 3.x + Uvicorn | HTTPS on port 6443; `USE_HTTPS=false` for local dev |
| Config | pydantic-settings | All config from `backend/.env` |
| LLM / VLM | Qwen VLM | External Docker service at `/generate-with-image` |
| Agent layer | ITFAgent / NARAgent | Schema-driven extraction, normalization, risk flagging |

## Storage

| Store | Purpose |
|---|---|
| MongoDB (Motor async) | Form metadata + extracted JSON results |
| MinIO | Original PNG images + result JSON blobs |

Storage schema is designed for downstream AI-ready use: LLMs, RAG, vector DBs, Elasticsearch.

## Infrastructure

| Concern | Approach |
|---|---|
| Containerization | Docker Compose (`docker compose up --build`) |
| SSL | Self-managed certs in `backend/certs/` |
| Deployment | Single-server, KEMRI network |

## Identified Gaps

These gaps are confirmed priorities for the roadmap:

### 1. Mobile / Smartphone Upload UX
- PI2 requirement: smartphone camera capture for form upload
- Current state: desktop drag-and-drop only (`UploadForm.jsx`)
- Need: mobile-first responsive layout (Pico CSS), camera input (`<input type="file" capture="environment">`), image compression before upload

### 2. Results Review & Correction UI
- No interface exists for users to inspect, edit, or reject extracted fields before committing to storage
- Risk flags and validation errors from agents are computed but not surfaced to the user
- Need: per-field review panel, inline edit, accept/reject workflow before final save

### 3. Authentication & Access Control (future)
- No user login or role-based access
- Defer until after core UX is solid; will likely use JWT + role enum matching target user table in `mission.md`

### 4. Batch Processing UI (future)
- Multi-file queue, per-job progress, bulk download not yet built
- Backend `/api/upload/status/{processing_id}` exists; frontend polling not wired

# Roadmap

Phases are ordered smallest-first. Each phase is shippable and independently testable.

---

## Phase 1 — Mobile-First UI Foundation
**Goal:** Make the frontend usable on smartphones.

- Apply Pico CSS as the responsive CSS baseline (`frontend/src`)
- Replace or augment Ant Design layout with Pico's semantic grid
- Add Google Fonts (modern, legible typeface)
- Make `UploadPage` and `HistoryPage` fully responsive at 375 px viewport
- Add `<input type="file" accept="image/png,image/jpeg" capture="environment">` for camera capture on mobile

---

## Phase 2 — Upload Flow Wired End-to-End
**Goal:** Connect the frontend upload UI to the backend processing pipeline.

- Wire `UploadForm.jsx` → `POST /api/upload/`
- Poll `GET /api/upload/status/{processing_id}` and display job progress
- Show success/failure feedback on screen after processing completes
- Basic image compression (client-side, before upload) to support mobile connectivity

---

## Phase 3 — Results Review UI
**Goal:** Let users inspect and correct extracted data before it is committed.

- Display extracted fields returned from the backend in a readable panel
- Surface agent risk flags and validation errors inline
- Allow per-field inline editing
- Add accept / reject workflow: accepted results are written to MongoDB + MinIO; rejected results are discarded or flagged

---

## Phase 4 — History & Stats Pages
**Goal:** Give data managers and PIs visibility into the processing pipeline.

- `HistoryPage`: paginated list of processed forms with status, form type, timestamp, and link to results
- `StatsPage`: processed counts by form type, coverage %, risk flag rates
- Stats polling already exists at `/api/stats` (5 s interval); connect to Redux `stats` slice

---

## Phase 5 — Batch Upload Queue
**Goal:** Support research coordinators uploading multiple forms at once.

- Multi-file drag-and-drop or file picker
- Per-file progress tracking (status badges: queued, processing, done, failed)
- Bulk download of results as JSON or CSV

---

## Phase 6 — Authentication & Role-Based Access
**Goal:** Secure the app for multi-user deployment at KEMRI.

- JWT login (username + password)
- Role enum: `nurse`, `coordinator`, `analyst`, `admin`
- Route guards in React; middleware guards on FastAPI routes
- Admin dashboard: user management, pipeline health

---

## Phase 7 — AI-Ready Data Export
**Goal:** Make stored data consumable by downstream AI systems.

- Structured JSON export compatible with LLM context windows
- Elasticsearch index schema for full-text + faceted search over extracted fields
- Vector embedding endpoint (embed extracted text per form for RAG use)

---

## Deferred / Under Discussion

- Audit trail / change history for reviewed/corrected records
- Offline-first PWA mode for low-connectivity wards
- Multi-language UI (Swahili)
- Direct DHIS2 / OpenMRS integration

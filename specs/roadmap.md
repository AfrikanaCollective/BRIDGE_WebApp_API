# Roadmap

Phases are ordered smallest-first. Each phase is shippable and independently testable.

---

## Phase 1 — Mobile-First UI Foundation
**Goal:** Make the frontend usable on smartphones with consistent, accessible design across all pages.

### 1.1 Design System & Theme Setup
- **Create centralized design tokens** (`frontend/src/design-system/tokens.yaml`)
  - Define primary, secondary, and semantic color palette (see [Color Palette Spec](#color-palette))
  - Set typography scales with large, readable font sizes (base: 20px, h1: 36px)
  - Define spacing, border radius, and shadow scales
  - Create breakpoints for mobile (320px), tablet (768px), desktop (1024px)

- **Replace Ant Design with Pico CSS**
  - Apply Pico CSS as the responsive CSS baseline (`frontend/src/styles/responsive.css`)
  - Override Pico with design tokens (CSS custom properties)
  - Remove Ant Design dependencies from all `.jsx` components

- **Add Google Fonts**
  - Primary: `Inter` (body, UI text)
  - Secondary: `Poppins` (headings, emphasis)
  - Monospace: `JetBrains Mono` (code, data display)

### 1.2 Apply Design System to All `.jsx` Pages
- **Update `UploadPage.jsx`**
  - Use design tokens for spacing, colors, typography
  - Apply large font sizes: h2 (30px), body (18px), labels (16px)
  - Responsive grid layout: single column at 375px, two columns at 768px+
  - Add `<input type="file" accept="image/png,image/jpeg" capture="environment">` with styled file input
  - Camera capture button with primary color theme
  
- **Update `HistoryPage.jsx`**
  - Large, scannable table/list layout (20px base font)
  - Semantic color coding: success (green), warning (amber), error (red)
  - Responsive card view on mobile, table view on desktop
  - High-contrast text on backgrounds (primary colors from palette)

### 1.3 Responsive Layout & Mobile Optimization
- Apply semantic HTML structure (Pico CSS uses `<article>`, `<section>`, `<nav>`)
- Test all pages at 375px, 768px, and 1024px viewports
- Ensure touch-friendly button sizes (minimum 44px × 44px)
- Hide/show navigation based on breakpoint
- Vertical stacking on mobile, horizontal layout on desktop

### 1.4 Accessibility & Readability
- Font sizes:
  - H1: 36px (weight 700)
  - H2: 30px (weight 600)
  - H3: 24px (weight 600)
  - Body: 20px (weight 400)
  - Small/Caption: 14px (weight 500)
- Line height: 1.6 for body, 1.3 for headings
- Color contrast: all text ≥ 4.5:1 against backgrounds
- Focus states on all interactive elements (buttons, links, inputs)

___

## Color Palette Spec

### Primary Colors
| Name | Hex | Use Case |
|------|-----|----------|
| Primary 50 | #f0f9ff | Light backgrounds, hover states |
| Primary 500 | #0ea5e9 | Buttons, links, focus states |
| Primary 600 | #0284c7 | Button hover, active states |
| Primary 900 | #082f49 | Dark text on light backgrounds |

### Secondary Colors (Accent)
| Name | Hex | Use Case |
|------|-----|----------|
| Secondary 500 | #8b5cf6 | Secondary buttons, accents |
| Secondary 600 | #7c3aed | Secondary hover states |

### Semantic Colors
| Name | Hex | Use Case |
|------|-----|----------|
| Success | #10b981 | Valid inputs, success messages, green status |
| Warning | #f59e0b | Caution flags, amber status |
| Error | #ef4444 | Errors, validation failures, red status |
| Info | #3b82f6 | Information messages, blue status |

### Neutral Colors
| Name | Hex | Use Case |
|------|-----|----------|
| White | #ffffff | Page background, card backgrounds |
| Gray 50 | #f9fafb | Secondary backgrounds |
| Gray 100 | #f3f4f6 | Borders, dividers |
| Gray 500 | #6b7280 | Secondary text, disabled text |
| Gray 900 | #111827 | Primary text, headings |
| Black | #000000 | High-contrast text (use sparingly) |

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

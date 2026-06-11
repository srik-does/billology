---
description: "Task list for Bill Capture, Explanation & Discrepancy Pipeline — Hackathon Demo Spine"
---

# Tasks: Bill Capture, Explanation & Discrepancy Pipeline

**Input**: Design documents from `/specs/001-bill-pipeline/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Scope**: This is the **demo spine** — a deliberately narrowed build for a time-boxed demo.
It delivers the trustworthy core pipeline (capture → extract → verify → explain → review/save)
plus category suggestion and the two highest-impact secondary features (dual-path Q&A, dashboard),
then stops. Work that is fiddly or low-payoff for a demo is moved to **Deferred / Cut** at the
bottom (with original task IDs preserved for traceability), to be pulled back in if time remains.

**Tests**: Minimal. Only one protective test is kept — the discrepancy true-positive / no-false-
positive suite (T023) — because a false overcharge flag in the demo is catastrophic and the
constitution (Principle II) mandates it. All other tests are deferred.

**Build order**: strictly top-to-bottom. Phases 3–6 are the core (Principle V "Feature-1 is the
product"); Phase 7 seeds demo data; Phases 8–9 are the wow; Phase 10 is the one privacy claim
you'll make on stage.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- Paths follow plan.md: `backend/` (FastAPI) and `mobile/` (Expo).

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create monorepo structure `backend/` and `mobile/` per plan.md Project Structure
- [X] T002 Initialize backend Python project: `backend/requirements.txt` (fastapi, uvicorn, pydantic, supabase, fastembed, groq, pytesseract, pdfplumber, pdf2image, pillow, numpy, python-dotenv, pytest) and a venv
- [X] T003 [P] Initialize Expo app in `mobile/` with expo-camera, expo-image-picker, expo-document-picker, react-native-gifted-charts; set `mobile/app.json`
- [X] T004 [P] Implement `backend/src/config.py` loading env (SUPABASE_URL/KEY/BUCKET, GROQ_API_KEY/MODEL, EMBEDDING_MODEL/DIM)
- [X] T005 [P] Create `backend/.env.example` and `mobile/.env.example` (per quickstart.md)

> Cut from setup: lint/format config (orig T004) — not demo-critical.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 Author DB migration `backend/src/db/migrations/001_init.sql`: enable `vector` + `pg_trgm`; create `bills`, `line_items`, `source_artifacts`, `discrepancy_flags`, `explanations`, `categories` per data-model.md; `embedding vector(384)`; indexes on `(merchant,bill_date,total_amount)`, `category_id`, `bill_date`, HNSW `vector_cosine_ops`
- [X] T007 [P] Author seed migration `backend/src/db/migrations/002_seed_categories.sql` (Telecom/Recharge, Groceries, + a few common categories)
- [X] T008 [P] Implement Pydantic schemas in `backend/src/models/` (Provenance enum, TracedValue, LineItem, Bill, DiscrepancyFlag, Explanation, Category) per data-model.md
- [X] T009 [P] Implement INR number parser `backend/src/services/parsers/inr.py` (`parse_inr` → `Decimal`; lakh/crore grouping, ₹/Rs./INR)
- [X] T010 Implement persistence layer `backend/src/services/persistence.py` (Supabase Postgres client + Storage upload/signed-URL for private `bills` bucket)
- [X] T011 [P] Implement `backend/src/services/embedding_service.py` (fastembed `BAAI/bge-small-en-v1.5`, 384-d; assert dim == EMBEDDING_DIM)
- [X] T012 [P] Implement provider-swappable `backend/src/services/llm_service.py` interface + Groq impl skeleton (`explain`, `suggest_category`, `classify_question`, `question_to_query`, `summarize_results`)
- [X] T013 Create FastAPI app skeleton `backend/src/main.py` (router wiring, error-handling middleware, `/docs`)
- [X] T014 [P] Create mobile API client `mobile/src/api/client.ts` and navigation skeleton `mobile/src/navigation/`

> Deferred from foundational: INR parser unit test (orig T016) — pull back if time permits.

**Checkpoint**: Foundation ready.

---

## Phase 3: User Story 1 - Provide a bill (Priority: P1) 🎯 MVP

**Goal**: Submit a bill as **PDF, pasted text, or one clean image** and get a single structured
candidate; all figures extracted (never generated), each with provenance + source trace.
Unreadable / non-bill input is declined gracefully rather than fabricated.

**Independent Test**: Submit a telecom PDF, the same bill as text, and one clean grocery image →
each yields a structured candidate; multi-page PDF treated as one bill; a non-bill input returns a
"couldn't read a bill" response with no fabricated fields.

**Demo narrowing**: PDF + text + **single clean image** only. Multi-image assembly and image-quality
gating are cut/deferred (see bottom).

- [X] T015 [P] [US1] Implement PDF extraction `backend/src/services/extraction/pdf.py` (pdfplumber text+tables; all pages = one bill; pdf2image→OCR fallback optional)
- [X] T016 [P] [US1] Implement pasted-text extraction `backend/src/services/extraction/text.py` (normalize → line tokens)
- [X] T017 [P] [US1] Implement single clean-image OCR `backend/src/services/extraction/ocr.py` (Tesseract + basic Pillow preprocess; per-value source_ref + confidence)
- [X] T018 [US1] Implement per-type parsers `backend/src/services/parsers/telecom.py` and `backend/src/services/parsers/grocery.py` → structured candidate (line items, totals, tax fields) with `provenance=extracted` + source_ref; uses `parse_inr`
- [X] T019 [US1] Implement extraction orchestrator `backend/src/services/extraction/__init__.py` (route by input kind → one candidate; multi-page PDF as one bill)
- [X] T020 [US1] Implement `POST /bills:process` in `backend/src/api/bills.py` returning the structured candidate
- [X] T021 [US1] Add a minimal non-bill confidence-floor guard in `backend/src/services/extraction/__init__.py` + `backend/src/api/bills.py`: when no total/line items can be located or overall extraction confidence is below a basic threshold, return a graceful `422` "couldn't read a bill" response instead of emitting fabricated fields (cheap FR-021 — full duplicate/non-bill detection stays deferred, orig T052–T055)
- [X] T022 [US1] Mobile capture screen `mobile/src/screens/CaptureScreen.tsx` (single-image camera, PDF/image picker, pasted text) → `/bills:process`; surface the "couldn't read a bill" decline

**Checkpoint**: Structured candidate from any of the three input paths; non-bill input declined — MVP.

---

## Phase 4: User Story 4 - Detect discrepancies (Priority: P1) 🎯 "caught an overcharge"

**Goal**: Flag only provable inconsistencies (sum mismatch, duplicate item, internal tax-math
error) with conflicting figures; never flag legitimate/unverifiable cases.

**Independent Test**: An inconsistent bill is flagged with figures; a clean bill and a legitimately
non-summing bill are flagged with nothing; total-only bill → "nothing to verify."

- [X] T023 [P] [US4] Discrepancy unit tests — true positives AND absence of false positives (rounding/carried-forward/deposit not flagged; tax-not-verifiable not flagged; total-only → nothing_to_verify) in `backend/tests/unit/test_discrepancy.py` *(recommended; cut only if truly out of time — protects the wow moment + Principle II)*
- [X] T024 [P] [US4] Implement `backend/src/services/arithmetic_service.py` (deterministic sums + `rate×base` tax check, Decimal, each result traceable to source figures)
- [X] T025 [US4] Implement `backend/src/services/discrepancy_service.py` (`sum_mismatch`, `duplicate_item`, `tax_mismatch` carrying conflicting figures; legitimate-reason exclusions per FR-009; `nothing_to_verify` per FR-011)
- [X] T026 [US4] Wire arithmetic + discrepancy into `POST /bills:process`; include flags in CandidateResponse in `backend/src/api/bills.py`
- [X] T027 [US4] Mobile discrepancy list `mobile/src/components/DiscrepancyList.tsx` (flag + conflicting figures)

**Checkpoint**: Discrepancy detection works from the bill alone, no false positives.

---

## Phase 5: User Story 3 - Explain a bill (Priority: P1)

**Goal**: Plain-language explanation of each charge from already-extracted data; displayed numbers
always come from the record.

**Independent Test**: Each charge has a plain-language description; every displayed amount/date
matches the source exactly.

- [X] T028 [US3] Implement `explain()` Groq call in `backend/src/services/llm_service.py` (input = extracted structured fields only; output = descriptive text, no new numbers)
- [X] T029 [US3] Attach Explanation to candidate; implement `GET /bills/{id}` and include explanation in `backend/src/api/bills.py`
- [X] T030 [US3] Mobile bill-detail/explanation view `mobile/src/screens/BillDetailScreen.tsx`

**Checkpoint**: Bills explained in plain language with exact figures.

---

## Phase 6: User Story 5 - Review and save + category suggestion (Priority: P1) — gates everything downstream

**Goal**: User reviews extracted fields (low-confidence marked), edits (→ user_provided), sees a
**suggested category** they can accept or change to another seeded category, optionally edits the
date, and saves the canonical record (original artifact stored, embedding generated).
**Mandatory — Q&A and dashboard need saved records.**

**Independent Test**: Process a bill, see a suggested category, edit a field (marked user-provided),
accept or change the category, save, confirm the corrected record + its original artifact persist.

- [X] T031 [US5] Implement `POST /bills` (save) in `backend/src/api/bills.py`: accept reviewed candidate, set `provenance=user_provided` on edits, persist bills+line_items+flags+explanation, **persist `source_artifacts` and upload the original bill file to the private Supabase Storage bucket (signed-URL) via T010**, then generate + store embedding. Extract the persistence + embedding-rendering logic into a shared writer (e.g. `backend/src/services/bill_writer.py`) so the seed script (T034) reuses it verbatim.
- [X] T032 [US6] Implement `suggest_category()` Groq call in `backend/src/services/llm_service.py` (input = merchant + line items + seeded category list; returns a category from the list, or falls back to a default if none fits), and wire it into `POST /bills:process` so the candidate carries a suggested category in `backend/src/api/bills.py`
- [X] T033 [US5] Mobile review-and-edit screen `mobile/src/screens/ReviewScreen.tsx` — field rows with low-confidence marking + edit, an **editable date field** (no elaborate provenance UI), and the **suggested category pre-selected** with accept / change (pick another seeded category) options

**Checkpoint**: ✅ Core P1 pipeline complete and demo-ready (the constitutional product).

> Folded in here (trimmed): editable date field (from orig T050/T051, minus provenance ceremony).
> Out of demo scope: creating a brand-new category — the review screen only accepts the suggestion or picks from the seeded list (no `POST /categories` backend in the spine). Near-duplicate warning also cut (orig T048/T049).

---

## Phase 7: Demo Data Seeding (Demo-Critical Infrastructure)

**Purpose**: Q&A and dashboard are empty (and undemoable) without a corpus of saved records. This
phase creates that corpus. **Must run before any demo of Phase 8 or Phase 9.**

- [X] T034 Create demo seed script `backend/src/db/seed_demo_bills.py` that inserts ~12–15 realistic **saved** bills (telecom/recharge + grocery) spanning multiple months and categories, each with line items, provenance flags, and a generated embedding; idempotent and runnable via PowerShell. Document the run command in quickstart.md. **Acceptance**: the script MUST persist via the shared `bill_writer` helper from T031 (same embedding-rendering + provenance logic) — it must NOT insert rows its own way — so seeded and live-saved bills are byte-for-byte consistent under semantic Q&A and dashboard aggregates.

**Checkpoint**: A realistic, consistent history exists for trend + semantic retrieval.

---

## Phase 8: User Story 9 - Ask questions about spending (Priority: P3) — 🌟 the wow

**Goal**: Dual-path grounded Q&A — numeric via parameterized SQL, semantic via pgvector;
unanswerable → explicit "not available." (Semantic path also covers "find a bill," so dedicated
search is intentionally cut.)

**Independent Test**: With the seeded corpus, "How much did I recharge last time?" → grounded
numeric answer; "which bill had a late fee?" → real record(s); a question with no records → honest
"not available."

- [X] T035 [US9] Implement numeric path in `backend/src/api/qa.py` (`classify_question` → `question_to_query` parameterized + allowlisted schema → backend executes SQL → exact numbers; LLM never computes)
- [X] T036 [US9] Implement semantic path in `backend/src/api/qa.py` (fastembed embed → pgvector cosine retrieve real rows → optional `summarize_results`); unanswerable → explicit message
- [X] T037 [US9] Mobile Q&A chat screen `mobile/src/screens/QAChatScreen.tsx`

**Checkpoint**: Grounded dual-path answers; doubles as bill search.

---

## Phase 9: User Story 8 - Spending dashboard (Priority: P3) — cheap + high-impact

**Goal**: Category breakdown + monthly trend from saved records only (SQL aggregates + charts).

**Independent Test**: With the seeded corpus, dashboard shows spending by category and over time,
derived solely from saved records.

- [X] T038 [US8] Implement `GET /dashboard/by-category` and `GET /dashboard/monthly` SQL aggregates in `backend/src/api/dashboard.py`
- [X] T039 [US8] Mobile dashboard `mobile/src/screens/DashboardScreen.tsx` (gifted-charts donut + trend)

**Checkpoint**: Visual spending insight.

---

## Phase 10: Demo-Critical Polish

- [ ] T040 Privacy/security pass: confirm Supabase Storage bucket is **private** with signed URLs only (originals uploaded in T031), and the mobile client never calls Groq or the DB directly — so the single-trust-boundary claim (Principle IV) is true and demoable

> Cut from polish: structured logging, perf tuning, READMEs (orig T067, T069, T070). Run-quickstart (orig T066) optional smoke test if time permits.

---

## Deferred / Cut (pull back "if time remains")

Original task IDs preserved for traceability against the full plan.

**Deferred (robustness, not demo-critical):**
- INR parser unit test (orig T016)
- US2 image quality / recapture gate (orig T042, T043)
- US11 full duplicate-bill + non-bill detection (orig T052–T055) — *the cheap non-bill guard is in T021; the full version matters only if a judge tries hard to break it*
- Broader test suites: extraction units + contract tests (orig T017–T019, T027, T033, T037–T038, T046, T056, T059, T063), arithmetic unit test (orig T027)
- Quickstart full validation + logging + perf + docs (orig T066, T067, T069, T070)
- Full date-provenance handling (orig T050 — kept only the editable field)

**Cut for v1 (low payoff for effort):**
- US2 multi-image assembly + reorder/merge-safety (orig T044, T045) — fiddly, low demo payoff
- US6 create-new category + near-duplicate warning (orig T048, T049) — suggestion + pick from seeded list suffices; no `POST /categories` in the spine
- US10 dedicated search (orig T063–T065) — semantic Q&A covers "find a bill"

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)** must finish first; Phase 2 blocks everything.
- **P1 core (Phases 3–6)** in strict order: US1 produces the candidate that US4/US3/US5 consume; the non-bill guard (T021) extends the `/bills:process` path (T020); the category suggestion (T032) depends on the `/bills:process` candidate (T020) and the `llm_service` skeleton (T012); US5 save (T031) gates all downstream and owns the shared `bill_writer` helper.
- **Demo seeding (Phase 7)** depends on the save/embedding path being correct (T031, T011) — it reuses the `bill_writer` helper. Must complete before Phases 8–9 are demoed.
- **Phase 8 (Q&A)** and **Phase 9 (dashboard)** both require saved records (Phase 6) + the seeded corpus (Phase 7); otherwise independent of each other.
- **Phase 10 (privacy pass)** last; verifies the T031 artifact upload.

### Within stories
- T023 (discrepancy test) before/with T025.
- Models → services → endpoints → mobile UI.

### Parallel Opportunities
- Setup: T003, T004, T005.
- Foundational: T007, T008, T009, T011, T012, T014 (after T006 for schema-dependent work).
- US1 extraction: T015, T016, T017 in parallel.
- US4: T023 (test) parallel with T024.
- Phase 6: T031 (save + writer) and T032 (suggest_category) touch different concerns and can proceed in parallel before T033 (review screen) consumes both.
- Split by layer: one dev on `backend/`, one on `mobile/` once contracts are stable.

---

## Parallel Example: User Story 1

```bash
# Extraction implementations together:
Task: "PDF extraction in backend/src/services/extraction/pdf.py"
Task: "Text extraction in backend/src/services/extraction/text.py"
Task: "Single clean-image OCR in backend/src/services/extraction/ocr.py"
```

---

## Implementation Strategy

### The spine (recommended demo path)
1. Phase 1 + 2 — setup + foundation.
2. Phases 3–6 — the trustworthy core pipeline + category suggestion. **This alone is a credible demo** (Principle V).
3. Phase 7 — seed the demo corpus (do this before showing Q&A/dashboard).
4. Phase 8 — dual-path Q&A (the wow).
5. Phase 9 — dashboard (cheap, visual).
6. Phase 10 — lock the privacy claim.

### If time remains
Pull from Deferred first (the full duplicate/non-bill guards and the image-quality gate are the
most demo-protective), then Cut items.

### Notes
- [P] = different files, no incomplete-task dependencies.
- T023 protects the discrepancy wow — write it and make it fail before T025.
- T031's shared `bill_writer` is the single source of save/embedding logic — both live saves and the T034 seed go through it; keep it that way so semantic Q&A is consistent.
- Phase 7 seeding is easy to forget and silently breaks the Q&A/dashboard demo — run it.
- Per Principle V, do not spend time on Deferred/Cut items before the P1 core (Phases 3–6) is solid.

# Implementation Plan: Bill Capture, Explanation & Discrepancy Pipeline

**Branch**: `001-bill-pipeline` | **Date**: 2026-06-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-bill-pipeline/spec.md`

## Summary

Billology ingests a bill (image, PDF, or pasted text), runs it through a **deterministic
extraction layer** (OCR / PDF text-layer / structured-text parsing) that is the sole source of
every monetary value, date, quantity, and line item. Backend code performs all arithmetic and
discrepancy detection from the bill's own internal consistency. An LLM is used **only as a
language tool** — explaining already-extracted figures, suggesting a category from a controlled
list, and translating questions into queries — never to produce or compute a number.

The system is a mobile app (React Native / Expo) over a FastAPI backend that is the single trust
boundary: the frontend never talks directly to the LLM or the database. Each bill becomes one
canonical record in Supabase (Postgres + pgvector), with a per-field provenance flag
(extracted-from-source vs. user-provided) and a stored embedding. Downstream features —
review/save, dashboard aggregates, and a dual-path (numeric SQL vs. semantic vector) Q&A — are
all views over that single record.

## Technical Context

**Language/Version**: Python 3.11+ (backend); TypeScript / React Native via Expo SDK 51+ (mobile)

**Primary Dependencies**:
- Backend: FastAPI, Uvicorn, Pydantic v2, `supabase` (supabase-py), `fastembed`, Groq Python SDK, `pytesseract` (+ Tesseract OCR engine), `pdfplumber`, `Pillow`, `pdf2image`
- Mobile: Expo (expo-camera, expo-image-picker, expo-document-picker), `react-native-gifted-charts`, a typed API client (fetch/axios)

**Storage**: Supabase Postgres with `pgvector` (canonical records, line items, categories, embeddings); Supabase Storage (original images/PDFs, private bucket)

**Testing**: `pytest` (backend — extraction, arithmetic, discrepancy rules, contract tests); Jest + React Native Testing Library (mobile components/flows)

**Target Platform**: iOS 15+ / Android 10+ (Expo); Linux/container backend (developed on Windows + PowerShell)

**Project Type**: Mobile + API (Expo client + FastAPI service)

**Performance Goals**: A typical single-page bill processed into its explained, verified record in **~10 s** under normal conditions (SC-009); dashboard and numeric Q&A answered via SQL aggregates in <1 s for a single user's history.

**Constraints**:
- Backend is the only component that calls the LLM or the database (single trust boundary).
- LLM (Groq, cloud) MUST receive only already-extracted structured fields needed for the language task — never raw images and never more bill content than the step requires (Principle IV, NFR-Privacy).
- All arithmetic and discrepancy checks run in deterministic, unit-tested code paths — never the LLM (Principles I, II; FR-022).
- Discrepancy detection uses only the current bill's internal consistency — no prior-bill history (FR-010).
- pgvector column dimension MUST equal the fastembed model's output dimension (pinned: 384).
- Indian number formatting (lakh/crore grouping, ₹) MUST parse correctly (NFR-Localization).
- Setup/run instructions target Windows + PowerShell.

**Scale/Scope**: Single user, single device (per spec Assumptions); initial supported bill types = **telecom/recharge-provider bills and printed grocery receipts** (FR-023). ~5–6 screens (capture, review/edit, bill detail, dashboard, Q&A chat, history/search).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | How this plan complies |
|---|-----------|------------------------|
| I | Numbers Are Never Invented | Deterministic extraction layer (OCR/pdfplumber/text parser) is the sole producer of all figures; each is stored with a source trace. LLM `explain()` receives already-extracted values and may not emit numbers (validated — see Phase 1 contracts). Arithmetic lives in `arithmetic_service`. |
| II | Discrepancies Must Be Provable, Not Guessed | `discrepancy_service` flags only: line-items≠total, duplicate line item, and `rate×base≠stated tax` (internal-only tax check per clarify). Legitimate non-summing reasons and unverifiable tax are not flagged. Every flag carries its conflicting figures. Tests cover true positives **and** absence of false positives. |
| III | One Structured Data Model Is the Source of Truth | A single `bills` canonical record (+ `line_items`) is persisted once; dashboard, search, and Q&A read from it via SQL/vector queries. No feature re-parses the raw bill. |
| IV | Privacy by Default | FastAPI is the only trust boundary; the mobile client never contacts Groq or the DB directly. Groq calls send only the minimal extracted fields for the language task (documented per-call in `research.md`/contracts). Originals live in a private Supabase Storage bucket. Cloud use (Supabase, Groq) is a deliberate, documented choice recorded here. |
| V | Feature-1 Is the Product | Build order prioritizes the core pipeline (capture → extract → verify → explain → review → save) before dashboard/Q&A (P3). Phasing and tasks keep secondary features from competing with core completeness. |
| VI | Q&A Answers Are Grounded | Numeric path: `question_to_query` → parameterized SQL → exact Postgres numbers (LLM never computes). Semantic path: fastembed + pgvector retrieval of real records → optional summary over retrieved rows only. Unanswerable → explicit "not available." |

**Technology & Data Constraints gate**: Structured-model-first ✅; computation-in-code ✅; traceability (per-field source ref) ✅; data-minimization on cloud calls ✅ (documented); tech stack now decided and recorded here ✅.

**Result: PASS** — no violations; Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-bill-pipeline/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (OpenAPI + per-endpoint contracts)
│   ├── openapi.yaml
│   ├── bills.md
│   ├── categories.md
│   ├── dashboard.md
│   └── qa.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── main.py                  # FastAPI app + router wiring
│   ├── config.py                # env: Supabase URL/key, Groq key, embedding model
│   ├── models/                  # Pydantic schemas (Bill, LineItem, Discrepancy, ...)
│   ├── api/
│   │   ├── bills.py             # submit/process, review/save, get bill
│   │   ├── categories.py        # suggestion + near-duplicate check
│   │   ├── dashboard.py         # category breakdown, monthly trend
│   │   └── qa.py                # dual-path Q&A endpoint
│   ├── services/
│   │   ├── extraction/          # ocr.py, pdf.py, text.py → structured candidate
│   │   ├── parsers/             # per-bill-type: telecom.py, grocery.py + INR number parsing
│   │   ├── quality_service.py   # image quality / low-light / confidence gating
│   │   ├── arithmetic_service.py# sums, tax math (deterministic, traced)
│   │   ├── discrepancy_service.py# provable flags only
│   │   ├── duplicate_service.py # merchant+date+total exact match
│   │   ├── embedding_service.py # fastembed (384-dim)
│   │   ├── llm_service.py       # provider-swappable; Groq impl
│   │   └── persistence.py       # Supabase Postgres + Storage
│   └── db/
│       └── migrations/          # SQL: tables, pgvector(384), indexes
└── tests/
    ├── contract/                # endpoint contract tests
    ├── integration/             # full pipeline per input type
    └── unit/                    # extraction, arithmetic, discrepancy (TP + no-FP), INR parsing

mobile/
├── src/
│   ├── screens/                 # Capture, Review, BillDetail, Dashboard, QAChat, History
│   ├── components/              # charts (gifted-charts), field rows w/ provenance/confidence
│   ├── api/                     # typed client to FastAPI
│   └── navigation/
├── app.json                     # Expo config
└── tests/
```

**Structure Decision**: Mobile + API. `mobile/` (Expo) is presentation and capture only; `backend/`
(FastAPI) owns extraction orchestration, all arithmetic, discrepancy logic, LLM access, embeddings,
and DB/storage — enforcing the single-trust-boundary constraint (Principle IV). The
`services/extraction` + `services/parsers` split keeps deterministic value production isolated from
`llm_service`, enforcing Principle I structurally.

## Complexity Tracking

> No Constitution Check violations — section intentionally empty.

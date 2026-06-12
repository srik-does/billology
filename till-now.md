# Billology — Project Status (as of 2026-06-12, v2)

Bill analyzer: **v2 — vision-LLM extraction** (the model transcribes the bill image; every figure
re-validated in code; it never computes/invents numbers), FastAPI backend (single trust boundary),
Expo/RN mobile + web app served by the backend, Supabase Postgres+pgvector, Groq/Ollama-swappable
LLM. Deployed on Render (manual deploy): https://billology.onrender.com — repo mirrors:
code.swecha.org (origin) + github.com/srik-does/billology.

**Fallback to v1**: branch `v1-stable` + tag `v1-fallback` (commit `56a944c`, pushed to both
remotes) preserve the last pure-RapidOCR version. `VISION_EXTRACTION=false` also reverts the
running app to the deterministic pipeline without a rollback.

## Recently completed (all pushed to main)

| Commit | What |
|---|---|
| v2 | **Vision extraction**: image bills + fully scanned PDFs read by Groq `llama-4-maverick` (Ollama vision model when provider=ollama), transcribe-only prompt, code-side Decimal validation + raw-line traces, automatic fallback to the v1 OCR pipeline. Constitution 2.0.0 (Principle I redefined, Principle IV privacy trade-off documented). |
| `71c3eed` | OCR engine swapped Tesseract → **RapidOCR** (PP-OCRv4, local ONNX; Tesseract kept as fallback). Benchmark: `backend/scripts/compare_ocr.py` (pass a real image path to compare engines). Now the fallback engine behind vision. |
| `c3ba824` | **Ask reliability**: save-time LLM tags/aliases (migration 004 — applied; backfill ran), fuzzy merchant match, hybrid keyword+vector retrieval, no more hard "No bills found" for merchant misses. |
| `1f28495` | Large scanned PDFs: page-at-a-time rasterization (flat memory), 12-page cap with friendly 422, endpoints moved off the event loop (threadpool). |
| `1820b03` | Dockerfile: libgl1/glib for opencv (RapidOCR dep); models baked at build time. |
| `b532ac1` | **i18n: 13 languages** (en/hi/te + ta/kn/ml/bn/mr/gu/pa/or/as/ur) across mobile, web, backend templates. `test_i18n.py` enforces backend completeness. |
| `60e7926` | Dashboard: stat cards (this month, % vs last, top category), SVG donut (web), top merchants, animations, busy/error states, decline reasons surfaced on mobile. |
| `eae0a55` | **UI redesign**: mobile bottom tab bar with icons, gradient hero capture screen, banners for errors, chat-bubble Ask, card shadows/design tokens; web two-column layout + gradient header. |

Backend tests: 72 passing (`venv\Scripts\python.exe -m pytest backend\tests -q` from repo root).

## Known limitations / accepted risks

- **v2 privacy trade-off**: full bill images go to Groq for vision extraction (constitution
  v2.0.0, Principle IV — deliberate and documented; local-only via Ollama or
  `VISION_EXTRACTION=false`). Discrepancy flags from vision figures use a fixed 0.9
  confidence (no per-token OCR scores), so a rare mis-transcribed digit could surface as a
  "proven" flag.
- **Render free tier ≈100s proxy timeout**: a 9-page scanned PDF still times out there
  (server now survives it gracefully). Proper fix = background-job pattern
  (upload → job id → client polls). Not built yet.
- The 10 new language translations are **machine-authored, pending native-speaker review**
  (marked in source comments).
- Merchant extraction can grab a header line (saw "Retail Invoice" as merchant on a real
  department-store bill) — parser/labeling improvement candidate; tags compensate in search.
- Embedding model is English-only (`bge-small-en-v1.5`); swap to a multilingual fastembed
  model + re-run `backend/scripts/backfill_tags.py` if Ask should work in Indian languages.
- Rotate the Supabase service key + Groq key if not already done (they briefly sat in a
  tracked file locally; never committed).

## Open discussion (user's queue)

1. ~~Image reading / OCR feedback~~ — resolved by v2 vision extraction; awaiting user's
   real-bill testing of the new path.
2. UI iteration — redesign shipped; awaiting user's visual feedback.
3. Background jobs for long PDFs (decide if needed for real users).
4. Privacy hardening (constitution v2 defers it; revisit before any public launch).

## Dev quickstart

- Backend: `cd backend; ..\venv\Scripts\python.exe -m uvicorn src.main:app --reload`
  (env in `backend/.env`; web app served at `/`).
- Mobile: `cd mobile; npm start` (Expo; `EXPO_PUBLIC_API_BASE` points at the backend).
- Deploy: push to GitHub, then Render → Manual Deploy (auto-deploy is OFF).
- DB migrations: run `backend/src/db/migrations/*.sql` in Supabase SQL editor (001–004 applied).

# Billology — Project Status (as of 2026-06-12)

Bill analyzer: deterministic extraction (numbers never come from the LLM), FastAPI backend
(single trust boundary), Expo/RN mobile + web app served by the backend, Supabase
Postgres+pgvector, Groq/Ollama-swappable LLM. Deployed on Render (manual deploy):
https://billology.onrender.com — repo mirrors: code.swecha.org (origin) + github.com/srik-does/billology.

## Recently completed (all pushed to main)

| Commit | What |
|---|---|
| `71c3eed` | OCR engine swapped Tesseract → **RapidOCR** (PP-OCRv4, local ONNX; Tesseract kept as fallback). Benchmark: `backend/scripts/compare_ocr.py` (pass a real image path to compare engines). |
| `c3ba824` | **Ask reliability**: save-time LLM tags/aliases (migration 004 — applied; backfill ran), fuzzy merchant match, hybrid keyword+vector retrieval, no more hard "No bills found" for merchant misses. |
| `1f28495` | Large scanned PDFs: page-at-a-time rasterization (flat memory), 12-page cap with friendly 422, endpoints moved off the event loop (threadpool). |
| `1820b03` | Dockerfile: libgl1/glib for opencv (RapidOCR dep); models baked at build time. |
| `b532ac1` | **i18n: 13 languages** (en/hi/te + ta/kn/ml/bn/mr/gu/pa/or/as/ur) across mobile, web, backend templates. `test_i18n.py` enforces backend completeness. |
| `60e7926` | Dashboard: stat cards (this month, % vs last, top category), SVG donut (web), top merchants, animations, busy/error states, decline reasons surfaced on mobile. |
| `eae0a55` | **UI redesign**: mobile bottom tab bar with icons, gradient hero capture screen, banners for errors, chat-bubble Ask, card shadows/design tokens; web two-column layout + gradient header. |

Backend tests: 56 passing (`venv\Scripts\python.exe -m pytest backend\tests -q` from repo root).

## Known limitations / accepted risks

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

1. **Image reading / OCR feedback** — user analyzed the app and wants to discuss
   extraction quality changes (explicitly deferred by user).
2. UI iteration — redesign shipped; awaiting user's visual feedback.
3. Background jobs for long PDFs (decide if needed for real users).

## Dev quickstart

- Backend: `cd backend; ..\venv\Scripts\python.exe -m uvicorn src.main:app --reload`
  (env in `backend/.env`; web app served at `/`).
- Mobile: `cd mobile; npm start` (Expo; `EXPO_PUBLIC_API_BASE` points at the backend).
- Deploy: push to GitHub, then Render → Manual Deploy (auto-deploy is OFF).
- DB migrations: run `backend/src/db/migrations/*.sql` in Supabase SQL editor (001–004 applied).

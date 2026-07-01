# AGENTS.md

Guidance for AI coding agents (and new human contributors) working in this
repository. This is the committed, tool-agnostic counterpart to the local-only
`CLAUDE.md`; keep the two in sync when project conventions change.

## The one rule that overrides everything

> **Numbers come from the bill, never from the model's imagination.**

The project constitution (`.specify/memory/`, v2.0.0) makes this binding. When
writing or changing code:

- The LLM may **transcribe** what is printed on a bill image and **explain**,
  **categorize**, or **translate questions** — it must never **compute**,
  **estimate**, or **repair** a figure.
- Every value the vision LLM transcribes is re-validated in backend code
  (`parse_inr` → exact `Decimal`; unparseable values are **dropped, not fixed**)
  and traced to its raw source line.
- **All arithmetic and discrepancy detection run in code over `Decimal`s** — never
  in a prompt. Do not introduce a code path where the model returns a total.

If a change would let a model-produced number reach the user unvalidated, it is
wrong regardless of how well it tests.

## Architecture (where the trust boundary is)

```
Expo mobile app ──┐
Web app (at /) ───┴──► FastAPI backend  ← the ONLY trust boundary
                          ├── services/extraction/vision.py  (transcribe-only vision LLM)
                          ├── deterministic fallback: RapidOCR/Tesseract + parsers, pdfplumber
                          ├── arithmetic + discrepancy checks (Decimal, in code)
                          ├── llm_service  (Groq, provider-swappable; also Ollama)
                          ├── fastembed  (BAAI/bge-small-en-v1.5, 384-dim)
                          └── Supabase: Postgres + pgvector + private Storage
```

Clients **never** call Groq or the database directly. All auth, provider calls,
and DB access happen behind FastAPI. User-facing DB access runs under Postgres
RLS using the caller's forwarded JWT (see `backend/src/main.py`,
`services/request_context.py`).

## Repository layout

| Path | Contents |
|---|---|
| `backend/` | FastAPI service, extraction/parsing/LLM services, migrations, tests |
| `backend/src/` | `api/` routers, `services/`, `models/`, `db/`, `config.py`, `main.py` |
| `mobile/` | Expo (React Native) app |
| `specs/001-bill-pipeline/` | Spec, `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md` |
| `.specify/` | Spec-Kit config, templates, and the constitution |
| `docs/` | Strategy/process docs |

Read `specs/001-bill-pipeline/plan.md` (and its siblings) before making
non-trivial changes — it is the source of truth for stack and structure.

## Environment & commands (Windows + PowerShell dev)

Backend:

```powershell
cd backend
python -m venv venv ; .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env            # fill in real values
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Mobile:

```powershell
cd mobile
npm install --legacy-peer-deps
copy .env.example .env            # set EXPO_PUBLIC_API_BASE
npx expo start -c
```

Tests (run from `backend/`):

```powershell
pytest tests/ --cov=src
```

System deps for the fallback OCR path: Tesseract OCR and Poppler on PATH.
Apply `backend/src/db/migrations/*.sql` in order in the Supabase SQL editor
before first use.

## Conventions

- **Python:** ruff + mypy configured in `pyproject.toml` (line length 100,
  target py311). Type-annotate new code; keep functions pure where the value is
  a computed figure.
- **Secrets:** never commit them. `.env` is gitignored; gitleaks runs in
  pre-commit and CI. Add new config to `backend/.env.example` (with a
  placeholder value) and to `backend/src/config.py`.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `ci:`, `docs:` …);
  `cliff.toml` generates the changelog from them. Do not add AI attribution
  trailers to commit messages.
- **Graceful degradation:** the core extract → verify → explain flow must keep
  working with no API keys set (deterministic fallbacks). Don't make a feature
  hard-crash when a provider/env var is absent.

## Quality gates before you finish

- `ruff check` and `mypy` clean (see `pyproject.toml` scope).
- `pytest tests/` green.
- No secret material in the diff (gitleaks).
- Docs updated if behavior/config changed (`README.md`, `.env.example`,
  `USER_MANUAL.md`, and this file when conventions shift).

## CI/CD

- `.gitlab-ci.yml` on code.swecha.org runs lint, types, secret scan, dependency
  audit, and tests. Pushing a version tag (e.g. `v2.0.1`) additionally builds
  the Android APK and publishes a GitLab Release with the APK as an asset
  (requires a masked `EXPO_TOKEN` CI/CD variable).
- Backend deploys to Render via `render.yaml` (Docker, `backend/Dockerfile`).

# Contributing to Billology

Thanks for your interest! This project was built spec-driven with
[GitHub Spec-Kit](https://github.com/github/spec-kit); please keep changes consistent with the
feature specs in `specs/` and the constitution in `.specify/memory/constitution.md`.

## The one non-negotiable rule

**The LLM never produces or computes numbers.** Every monetary value, date, and quantity must come
from the deterministic extraction layer with a provenance flag and source trace. Arithmetic and
discrepancy detection run in backend code only. PRs that route figures through a model — however
convenient — will be declined.

## Getting started

1. Fork and clone the repo.
2. Follow the local setup in [README.md](README.md).
3. Install the hooks: `pip install pre-commit && pre-commit install`.

## Making changes

- Branch from `main`; use conventional commit messages (`feat:`, `fix:`, `docs:`, `chore:` …) —
  the changelog is generated from them (git-cliff).
- Lint and test before pushing:
  ```bash
  ruff check backend/src
  cd backend && pytest tests/ --cov=src
  ```
- For anything DB-, LLM-, or device-dependent, verify against the **real running system** (real
  HTTP, real Supabase rows) — "tests pass" alone is not proof.
- Update the relevant spec under `specs/` when behavior changes.

## Reporting issues

Open an issue with reproduction steps, expected vs. actual behavior, and (for extraction bugs) the
bill input that triggered it — redact anything personal first.

## Code of conduct

Be kind. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

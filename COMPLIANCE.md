# Compliance — file-by-file justification

This document maps each compliance criterion to the file(s) that satisfy it and explains what
each added file does and why it belongs in this repository.

| Criterion | File(s) | Justification |
|---|---|---|
| Linter | `pyproject.toml` (`[tool.ruff]`), `mobile/.eslintrc.json` | Ruff lints the Python backend (pyflakes/pycodestyle/import order, py311 target); ESLint covers the React Native app with `eslint:recommended`. Both run in CI (`ruff` job) and pre-commit. |
| Type checker | `pyproject.toml` (`[tool.mypy]`) | Mypy checks `backend/src` (untyped defs checked, implicit Optional banned). Run by the CI `mypy` job. |
| Secret scanning | `.pre-commit-config.yaml` (gitleaks, detect-private-key), `.gitlab-ci.yml` (`gitleaks` job) | Gitleaks scans every commit locally and the full tree in CI, so credentials (Supabase/Groq keys) can never land in history. Complements `.gitignore`/`.dockerignore` rules that already exclude `.env`. |
| Dependency audit | `.gitlab-ci.yml` (`pip-audit`, `npm-audit` jobs) | pip-audit checks `backend/requirements.txt` against known CVEs; `npm audit` does the same for the Expo app. Advisory (allow_failure) so upstream advisories don't block hackathon iteration. |
| Coverage reporting | `backend/requirements.txt` (pytest-cov), `.gitlab-ci.yml` (`pytest` job with `--cov=src --cov-report=xml`, cobertura artifact) | Unit tests produce line coverage; GitLab parses the cobertura report and the `coverage:` regex surfaces the percentage on the pipeline. |
| Changelog automation | `cliff.toml`, `CHANGELOG.md`, `.gitlab-ci.yml` (`changelog` job) | git-cliff generates the changelog from conventional commits (which this repo uses); the CI job regenerates it on tags. `CHANGELOG.md` holds the v1.0.0 release notes. |
| Pre-commit hooks | `.pre-commit-config.yaml` | Runs ruff (with autofix), gitleaks, YAML checks, large-file and private-key guards before every commit. Install with `pre-commit install`. |
| GitLab CI pipeline | `.gitlab-ci.yml` | Four stages — lint, typecheck, test, security — wiring together every tool above. Lint and tests gate the pipeline; network-dependent scans are advisory. |
| AGPLv3 license | `LICENSE` | Full, unmodified GNU AGPL-3.0 text (the SPDX canonical copy). AGPL fits a network-served application: anyone offering a modified Billology as a service must share their changes. |
| Documentation | `README.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md` | README: what/why/architecture/setup/live demo. CONTRIBUTING: workflow plus the project's non-negotiable "LLM never produces numbers" rule. CODE_OF_CONDUCT: Contributor Covenant 2.1. SECURITY: reporting channel and the trust-boundary design notes. |
| Project description | (GitLab project setting — not a file) | Set in GitLab → Settings → General. Suggested text: "AI-powered bill analyzer: deterministic extraction + provable discrepancy checks; the LLM explains but never produces a number. FastAPI · Expo · Supabase pgvector · Groq." |
| Git tags | tag `v1.0.0` | Annotated release tag marking the feature-complete hackathon build described in CHANGELOG 1.0.0. |
| Spec-Kit setup / constitution / templates | `.specify/` (pre-existing) | Spec-Kit scaffolding, the project constitution (`.specify/memory/constitution.md`), and standard templates — present since the first commit. |
| Feature specs | `specs/001-bill-pipeline/` | The bill-pipeline feature spec (spec, plan, research, data model, API contracts, quickstart, tasks). Restored to the standard `specs/` path (it was temporarily named `spec-kit/`). |

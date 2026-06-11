# Security Policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately via the repository's confidential issue feature
(or directly to the maintainer) rather than opening a public issue. Include reproduction steps and
impact. You can expect an acknowledgement within a few days.

## Design notes relevant to security

- **Single trust boundary:** only the FastAPI backend talks to Supabase and the LLM provider; the
  clients hold no database or provider credentials.
- **Secrets:** all credentials live in environment variables (`backend/.env`, never committed —
  enforced by `.gitignore`, `.dockerignore`, and gitleaks in pre-commit/CI).
- **Storage:** original bill artifacts are stored in a private Supabase bucket; access is via
  short-lived signed URLs minted by the backend.
- **LLM containment:** model output is never executed or used as a source of figures; structured
  outputs are validated against allowlists before use.
- **Known demo limitations:** the deployed demo has no per-user authentication (single-tenant
  hackathon scope) and exposes data-clearing endpoints by design for demo resets.

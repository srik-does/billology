# Changelog

All notable changes to Billology are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the file is regenerable from conventional
commits with [git-cliff](https://github.com/orhun/git-cliff) (`cliff.toml`).

## [1.0.0] - 2026-06-11

### Features

- Deterministic bill extraction: image OCR (Tesseract with upscale/contrast preprocessing),
  PDF text layer (pdfplumber) with OCR fallback, and pasted-text parsing — every figure traced
  to its source line with a provenance flag.
- Provable discrepancy detection (sum mismatch, duplicate charge, tax mismatch) with
  multi-hypothesis reconciliation so discounts and tax-inclusive layouts are not false-flagged.
- LLM structure labeling with a deterministic acceptance gate (labels accepted only when
  arithmetically more consistent than the heuristic parse); the LLM never produces figures.
- Plain-language explanations and category suggestions from amount-free payloads.
- Review & save with user-provided provenance for edited fields; originals archived to private
  Supabase Storage.
- Dual-path Q&A: numeric (LLM-derived validated intent → code computes over real rows) and
  semantic (fastembed + pgvector retrieval → grounded summary).
- Spending dashboard (by-category and monthly SQL aggregates).
- Bill history with merchant search, category filter, per-bill delete, and clear-all.
- Web app (served by the backend) covering the full flow; Expo mobile app with a consistent theme.
- Render deployment blueprint (Docker with Tesseract/Poppler).

### Bug fixes

- GST summary-table rows no longer poison total/tax capture; OCR keyword tolerance ("Tota!");
  total-candidate ranking; GSTIN lines excluded from tax capture.
- Missing `python-multipart` dependency that broke multipart endpoints in clean deployments.
- Q&A numeric path no longer returns the global total for filtered questions.

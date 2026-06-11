# Phase 0 Research: Bill Pipeline

All decisions below resolve the open technical choices left by the plan input. The user's
technical brief fixed most of the stack (Expo, FastAPI, Supabase+pgvector, Groq, fastembed); this
document pins the remaining unknowns and records the privacy-relevant data-flow decisions the
constitution requires to be documented.

## 1. OCR engine for images

- **Decision** *(revised 2026-06-11; originally Tesseract)*: RapidOCR (PP-OCRv4 detection +
  English recognition on ONNX Runtime, CPU) as the primary engine, run on the backend.
  Tesseract via `pytesseract` is retained as an automatic fallback if RapidOCR fails to load
  or errors at runtime.
- **Rationale**: Same trust-boundary properties as Tesseract — fully local, deterministic
  pixel recognition, per-line confidence (Principles I and IV) — with substantially better
  accuracy on phone photos of receipts, which extraction-quality testing showed was the
  blocking weakness (the risk accepted at the bottom of this document materialized).
  Benchmarked in `backend/scripts/compare_ocr.py` on a synthetic receipt at three
  degradation tiers: at the severe tier RapidOCR recovers 8/10 key amount/ID tokens at 0.89
  mean confidence vs Tesseract's 7/10 at 0.52, with ~89% vs ~75% character accuracy and no
  junk lines; at clean/moderate tiers it is also ahead. Latency is comparable (~1.5–2s vs
  ~0.8s per receipt on CPU).
- **Operational notes** (all encoded in `services/extraction/ocr.py`):
  - The default ORT session config is effectively single-threaded (~22s/receipt); set
    `intra_op_num_threads` (≈8) to reach ~1.5s.
  - The angle classifier costs ~16s/receipt and only fixes upside-down text — disabled.
  - The engine must be a process-wide singleton created **before** any pytesseract
    subprocess call; sessions created after one run ~10x slower (observed on Windows).
  - Models (~20 MB, det + en rec) download from a ModelScope CDN on first use — they are
    baked into the Docker image at build time so runtime never reaches that CDN.
- **Alternatives considered**:
  - *Cloud OCR (Google Vision / AWS Textract)*: higher accuracy on thermal receipts but sends raw
    bill images off-device to a third party — rejected as the default per Principle IV. May be
    revisited as an explicit user opt-in (bring-your-own-key, like the LLM provider selection).
  - *PaddleOCR / EasyOCR / docTR*: same model family or comparable accuracy but heavyweight
    runtimes (PaddlePaddle / PyTorch); RapidOCR delivers the PP-OCR models on lightweight ONNX.
  - *Vision LLM for extraction*: directly violates Principle I (LLM would be producing numbers) —
    rejected outright.
- **Note**: Engine choice remains isolated behind `services/extraction/ocr.py`; callers and the
  `ExtractionResult` line model are unchanged.

## 2. PDF handling

- **Decision**: `pdfplumber` for text-layer + table extraction; `pdf2image` (Poppler) to rasterize
  pages that have **no** text layer, then route those pages through the same Tesseract path.
- **Rationale**: Most telecom/online PDFs carry a real text layer — parse it directly (lossless,
  no OCR error). Scanned-image PDFs fall back to OCR. All pages of a multi-page PDF are assembled
  into one logical bill (FR-002).
- **Alternatives**: PyMuPDF (fast, but pdfplumber's table/word-box API maps more cleanly to
  line-item extraction with source coordinates for traceability).

## 3. Structured text (pasted-text) parsing

- **Decision**: Deterministic per-bill-type parsers in `services/parsers/` (telecom, grocery)
  operating on normalized lines; a shared INR number tokenizer handles lakh/crore grouping.
- **Rationale**: Pasted text and OCR/PDF output converge to the same line-token model, so one set of
  type-specific parsers serves all three input formats and yields the single structured
  representation (FR-001).

## 4. Indian number formatting

- **Decision**: A dedicated `parse_inr(token)` helper that strips ₹/`Rs.`/`INR`, removes Indian
  digit-group commas (e.g. `1,00,000` and `1,23,456.78`), and returns a `Decimal`.
- **Rationale**: `Decimal` (never float) preserves exact paise for arithmetic and tax checks
  (Principle I traceability; FR-022). Indian grouping differs from Western thousands grouping, so a
  purpose-built parser is required (NFR-Localization). Unit-tested against lakh/crore cases.

## 5. Embedding model & vector dimension

- **Decision**: `fastembed` with `BAAI/bge-small-en-v1.5` → **384 dimensions**. The pgvector column
  is pinned to `vector(384)`.
- **Rationale**: Small, fast, CPU-friendly local model (no embedding data leaves the backend), good
  English retrieval quality for the semantic Q&A path. Pinning the dimension in the schema prevents
  the model/column mismatch called out in the brief.
- **Migration note**: Changing the embedding model later requires a migration + re-embed of stored
  records; the model id is centralized in `config.py`.

## 6. LLM (Groq) model & provider abstraction

- **Decision**: Access Groq through a thin `llm_service` interface (`explain`, `suggest_category`,
  `classify_question`, `question_to_query`, `summarize_results`). Default model: a Groq-hosted
  Llama-3.x instruct model, pinned in `config.py`.
- **Rationale**: The interface is provider-swappable (Groq now, frontier model later) so no caller
  depends on Groq specifics. Each method is constrained to a language task; none returns a numeric
  field that gets persisted.
- **Guardrails**:
  - `explain()` output is treated as descriptive text only; any numbers shown to the user come from
    the structured record, not from parsing the LLM's prose.
  - `suggest_category()` output is validated against the known-categories list (or flagged as a new
    suggestion) before use.
  - `question_to_query()` returns a **parameterized** query restricted to an allowlisted schema/columns;
    the backend executes it — the LLM never sees raw DB credentials and never returns answer numbers.

## 7. Privacy / data-minimization per cloud call (Principle IV — documented)

| Step | Data leaving the backend | To | Justification |
|------|--------------------------|----|---------------|
| Store original | Original image/PDF bytes | Supabase Storage (private bucket) | User's own archive; private bucket, signed URLs only. |
| Persist record | Canonical structured fields | Supabase Postgres | The single source of truth; same trust domain as storage. |
| `explain()` | Merchant + line-item descriptions + amounts/dates already extracted | Groq | Needed to phrase the explanation; no raw image, no account numbers beyond what a description requires. |
| `suggest_category()` | Merchant + line-item descriptions + known category names | Groq | Category inference only; no totals/account data required. |
| Q&A numeric | The user's natural-language question + DB schema description | Groq | To produce a parameterized query; no record values sent. |
| Q&A semantic | Question text (for embedding, local) + retrieved record snippets (for optional summary) | fastembed local; Groq only for summary | Embedding is local; summary sees only already-retrieved real rows. |

The mobile client sends bill inputs **only** to the FastAPI backend. It never calls Groq, Supabase,
or the DB directly.

## 8. Image quality / confidence gating

- **Decision**: `quality_service` computes a blur metric (variance of Laplacian via Pillow/numpy)
  and brightness; combined with Tesseract mean word-confidence, a bill below threshold triggers a
  recapture prompt (FR-005) rather than producing a low-confidence record.
- **Rationale**: Deterministic, cheap, on-backend. Thresholds are config constants tunable during
  testing. Per-field confidence flows into the review screen's low-confidence marking (FR-012).

## 9. Multi-image assembly & merge safety

- **Decision**: Images are ordered by capture sequence; the assembled page set is returned to the
  review screen for confirm/reorder/remove (FR-006a). Heuristic foreign-page detection: flag a page
  whose detected merchant/header differs from the others, or whose overlap with a neighbor is high.
- **Rationale**: Matches the clarified "both" decision (auto-detect + human confirm). Keeps the human
  review gate authoritative while catching obvious mis-merges automatically.

## 10. Discrepancy rules (deterministic, from clarify)

- **Sum check**: `Σ line_item.line_total` vs. extracted total. Mismatch beyond a rounding epsilon →
  flag, **unless** a legitimate reason field is present (carried-forward balance, deposit, explicit
  rounding line) — then not flagged (FR-009).
- **Duplicate line item**: identical description + amount appearing twice → flag.
- **Tax**: flag only when both tax rate and taxable base are extracted and `rate × base ≠ stated
  tax`; if rate or base absent → not verifiable → not flagged (clarify decision; FR-008).
- **No itemization**: total-only bill → "nothing to verify" (FR-011).
- Every flag carries the conflicting figures with their source traces (Principle II).

## 11. Duplicate-bill detection

- **Decision**: Exact match on `merchant` + `bill_date` + `total_amount` against saved bills → warn
  before save (FR-020, clarify "strict"). Implemented as a DB lookup in `duplicate_service`.

## 12. Category controlled list

- **Decision**: A `categories` table seeded with a small starter set (e.g. Telecom/Recharge,
  Groceries, plus a few common ones); `suggest_category()` chooses from existing names or proposes a
  new one. Near-duplicate detection on creation via case-insensitive + trigram/Levenshtein
  similarity (FR-014).

## Outstanding / deferred

- Observability (structured logging/metrics) — low impact for v1, deferred to implementation.
- ~~Tesseract thermal-receipt accuracy — accepted risk, mitigated by quality gate + human review;
  revisit if extraction quality testing shows it blocks the grocery-receipt use case.~~
  Materialized and resolved 2026-06-11: primary OCR engine swapped to RapidOCR (see §1).

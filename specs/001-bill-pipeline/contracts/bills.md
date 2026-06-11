# Contract: Bill submission, processing, review & save

Endpoints: `POST /bills:process`, `POST /bills`, `GET /bills/{id}`, `GET /bills/search`.
Schemas in [openapi.yaml](./openapi.yaml).

## POST /bills:process — submit & get candidate (no persistence)

Pipeline (all server-side, per Principles I–IV):

1. **Quality gate** (`quality_service`): low-light/blurry/low-confidence image → `409 {action: recapture}` (FR-005). Never returns a low-confidence record instead.
2. **Multi-input assembly**: multiple images or multi-page PDF combined into one logical bill; out-of-order/foreign-page heuristic may return `409 {action: confirm_merge}` with `assembled_pages` for review (FR-002, FR-006a).
3. **Extraction** (`extraction` + `parsers`): deterministic OCR/PDF/text → structured candidate. Sole producer of all figures; each gets `provenance=extracted`, `source_ref`, `confidence`.
4. **Non-bill detection**: if input isn't a recognizable bill → `422 Declined`, no fabricated data (FR-021). A genuine but unsupported layout is NOT declined → returned with `layout_supported=false` (best-effort).
5. **Arithmetic + discrepancy** (`arithmetic_service`, `discrepancy_service`): sum check, duplicate-item, internal-only tax check; total-only → `nothing_to_verify=true` (FR-008–FR-011). Flags carry conflicting figures.
6. **LLM language pass**: `explain()` + `suggest_category()` over already-extracted data only.
7. **Duplicate pre-check**: exact `merchant+bill_date+total_amount` match → `duplicate_warning` in body (FR-020).

**Invariant (testable)**: no number in the response originates from the LLM; every figure traces to a `source_ref` or is `user_provided`.

## POST /bills — persist reviewed candidate

- Body = candidate + user edits. Each edited field MUST arrive with `provenance=user_provided` and `source_ref=null` (FR-004); user-added date allowed (FR-015).
- If `duplicate_warning` was present and `acknowledged_duplicate != true` → `409` (re-warn).
- On save: persist `bills` + `line_items` + flags + explanation; generate `embedding` (fastembed, 384-d). Returns `201` with the saved `Bill`.

**Invariant**: persisted figures equal reviewed values exactly (SC-003).

## GET /bills/{id}

Returns the full canonical record (the single source all features read). No re-parsing of the raw artifact.

## GET /bills/search

Filter by `merchant`, `category_id`, `date_from/date_to` (FR-019). Reads saved records only.

## Contract tests (pytest)

- Same bill as image / PDF / text → equivalent candidate structure (FR-001).
- Low-light image → `409 recapture`, not a 200 record.
- Non-bill (e.g. selfie) → `422 Declined`, no figures.
- Non-summing-by-line bill → `sum_mismatch` flag with figures; rounding/carried-forward → no flag.
- Tax with rate+base wrong → `tax_mismatch`; tax amount only → no flag.
- Duplicate submit → `duplicate_warning`; save without ack → `409`.
- Edited field persists as `user_provided`.

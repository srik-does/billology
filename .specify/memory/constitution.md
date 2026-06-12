<!--
SYNC IMPACT REPORT
==================
Version change: 1.0.0 → 2.0.0 (MAJOR)
Rationale: v2 replaces local OCR with vision-LLM extraction as the primary
reader of bill images. Principle I is REDEFINED (the "never extracted by an
LLM" rule is removed — a multimodal model may now TRANSCRIBE printed values),
and Principle IV is REDEFINED (transmitting full bill images to the configured
LLM provider is now the documented default for image bills; the
privacy-minimization default is deliberately relaxed for v2). Both changes
invalidate prior compliance readings → MAJOR bump.

Principles (6 total):
  ~ I.   Numbers Are Never Invented → Numbers Come From the Bill, Never From
         the Model's Imagination (REDEFINED: vision-LLM transcription is now a
         permitted extraction stage; computing/estimating values remains
         forbidden; code-side validation, arithmetic, and traceability remain
         mandatory)
  = II.  Discrepancies Must Be Provable, Not Guessed (unchanged)
  = III. One Structured Data Model Is the Source of Truth (unchanged)
  ~ IV.  Privacy by Default → Privacy Is Documented, Not Assumed (REDEFINED:
         v2 accepts cloud vision extraction of full bill images as a
         deliberate, recorded product decision; local-only processing remains
         available via the Ollama provider)
  = V.   Feature-1 Is the Product (unchanged)
  = VI.  Q&A Answers Are Grounded (unchanged)

Sections:
  ~ Technology & Data Constraints — extraction stage rewritten for the
    vision-LLM primary path with the deterministic OCR/parser pipeline as
    fallback; stack recorded (was "deferred").

Templates requiring updates:
  ✅ .specify/templates/plan-template.md  — Constitution Check gate derives from
     this file dynamically; no hardcoded principle names. No edit required.
  ✅ .specify/templates/spec-template.md  — Generic; no principle references. No edit required.
  ✅ .specify/templates/tasks-template.md — Task categories derive from plan/spec; no edit required.

Follow-up TODOs:
  - Revisit Principle IV before any public/multi-user launch: privacy
    hardening (redaction, on-device options, retention limits) is deferred,
    not abandoned.
-->

# Billology Constitution

Billology is a mobile application where users upload images of their bills — grocery,
electricity, mobile recharge, or any other — and the app extracts the data from the
image, checks it for discrepancies, and explains the bill's terms in plain language.

## Core Principles

### I. Numbers Come From the Bill, Never From the Model's Imagination

Every monetary value, date, and quantity shown to the user MUST be read from the source
bill itself — by deterministic parsing (text layer, pasted text, OCR) or by a vision
model TRANSCRIBING what is printed on the image. A model used for extraction is a
transcriber: it MUST NOT compute, estimate, round, or fill in any value that is not
printed on the bill, and prompts MUST instruct it accordingly. Every model-transcribed
figure MUST be validated in code (strict currency/number parsing to `Decimal`; values
that fail validation are dropped, never repaired). Arithmetic (sums, tax checks, diffs)
is performed in code, not by the model. Any figure displayed MUST remain traceable to
the transcribed source line it came from.

**Rationale**: A bill app that misreports a number is worse than useless — it erodes the
trust the entire product depends on. v2 trades engine determinism for the far higher
read accuracy of vision models, but keeps the line that matters: the model may only
repeat what the bill says, and code remains the sole authority on validation and
arithmetic.

### II. Discrepancies Must Be Provable, Not Guessed

A flagged discrepancy MUST rest on verifiable internal consistency (line items don't sum
to the total, an item charged twice, tax math is wrong) or a concrete comparison against
the user's own prior bills — never on vague model intuition like "this seems high." If it
cannot be proven from the data, it is NOT flagged.

**Rationale**: False alarms train users to ignore real ones. Every flag must carry its
own evidence so the user can verify the claim against their bill.

### III. One Structured Data Model Is the Source of Truth

All features (explanation, categorization, dashboard, Q&A) MUST read from a single
canonical structured representation of each bill. Features are views over this model, not
independent pipelines. No feature re-parses the raw bill on its own.

**Rationale**: Multiple parsers produce multiple, divergent truths. A single canonical
model guarantees every feature sees the same numbers and that fixes propagate everywhere.

### IV. Privacy Is Documented, Not Assumed

Bills contain sensitive data (account numbers, addresses, consumption patterns). Every
transmission of bill content to an external service MUST be a deliberate, recorded
decision — this constitution and the relevant plan MUST state what is sent, to whom,
and why. **v2 decision on record**: bill images are sent in full to the configured LLM
provider (Groq by default) for vision extraction, because extraction accuracy is
prioritized over data minimization at this stage of the product. Users who require
local-only processing can select the Ollama provider with a local vision model. Steps
other than extraction MUST still receive only the portion of bill data they require.

**Rationale**: v1's minimize-by-default posture is deliberately relaxed for extraction
quality. What remains non-negotiable is honesty: no bill data leaves the system without
a documented decision, so the privacy trade-off is always visible and reversible —
privacy hardening is deferred, not abandoned.

### V. Feature-1 Is the Product

The bill-image → explanation + discrepancy pipeline is the core. Categorization,
dashboard, and Q&A are secondary and MUST NOT be built at the expense of the core. When
time is constrained, the core ships complete before secondary features are polished.

**Rationale**: The core pipeline is what makes Billology Billology. Secondary features add
value only on top of a complete, trustworthy core.

### VI. Q&A Answers Are Grounded

Natural-language questions about spending MUST be answered only from stored structured
records (preferably via precise querying), never from the model's memory or estimation. An
answer MUST correspond to actual records.

**Rationale**: An ungrounded "you spent about ₹X" is a fabricated number wearing a
conversational disguise — a direct violation of Principle I in another channel.

## Technology & Data Constraints

- **Structured model first**: Bill ingestion MUST produce the canonical structured model
  defined under Principle III before any feature consumes the data. Extraction and
  interpretation remain separate stages with a clear boundary: extraction produces values
  (transcribed from the bill), interpretation only explains them.
- **Extraction stages (v2)**: Image bills (and fully scanned PDFs) are read primarily by a
  multimodal vision LLM acting as a transcriber under Principle I. The deterministic
  pipeline (RapidOCR/Tesseract + keyword parsers) MUST be retained as an automatic
  fallback so a missing key, provider outage, or malformed response degrades accuracy
  rather than disabling image bills. PDF text layers and pasted text remain purely
  deterministic — a lossless text layer is never sent for vision re-reading.
- **Computation in code**: All arithmetic and consistency checks (sums, tax validation,
  duplicate detection, period-over-period diffs) MUST be implemented in deterministic code
  paths, with unit tests, not delegated to an LLM.
- **Traceability**: Each extracted field MUST retain a reference to its location/source in
  the original document (for vision extraction: the transcribed raw line) so any displayed
  figure can be traced back.
- **Data exposure (amended by Principle IV)**: Extraction may transmit full bill images to
  the configured LLM provider. Every other processing step MUST still receive only the
  portion of bill data it requires, and any new cloud call that transmits bill content
  MUST be documented in the relevant plan.
- **Technology stack (recorded)**: FastAPI backend (single trust boundary), React
  Native/Expo client, Supabase Postgres + pgvector + Storage, provider-swappable LLM
  (Groq cloud / Ollama local) for both vision extraction and language tasks.

## Development Workflow & Quality Gates

- **Compliance is mandatory**: Every spec, plan, and task MUST comply with these
  principles. `/speckit-analyze` MUST flag any violation as a finding before
  implementation proceeds.
- **Constitution Check gate**: Each plan MUST pass the Constitution Check gate. Any
  deviation MUST be recorded in the plan's Complexity Tracking table with a justification
  and the rejected simpler alternative — or the plan is revised to comply.
- **Test discipline for trust-critical paths**: Deterministic extraction, arithmetic, and
  discrepancy-detection logic MUST have tests asserting correctness and traceability.
  Discrepancy rules MUST have tests covering both true positives (provable issues) and the
  absence of false positives.
- **Prioritization**: When scope is cut under time pressure, the Feature-1 core pipeline
  (Principle V) ships complete before effort is spent polishing secondary features.

## Governance

This constitution supersedes other development practices for Billology. When a principle
and a convenience conflict, the principle wins.

- **Amendments**: Changes to this constitution MUST be made by editing this file, with a
  documented rationale and a version bump per the policy below. Dependent templates
  (`plan`, `spec`, `tasks`) MUST be reviewed for alignment as part of any amendment.
- **Versioning policy** (semantic versioning):
  - **MAJOR**: Backward-incompatible governance changes — a principle removed or
    redefined in a way that invalidates existing compliance.
  - **MINOR**: A new principle or section added, or materially expanded guidance.
  - **PATCH**: Clarifications, wording, and non-semantic refinements.
- **Compliance review**: All plans and the `/speckit-analyze` step MUST verify compliance.
  Justified, documented exceptions live in the plan's Complexity Tracking table; undocumented
  violations block progress.

**Version**: 2.0.0 | **Ratified**: 2026-06-09 | **Last Amended**: 2026-06-12

<!--
SYNC IMPACT REPORT
==================
Version change: TEMPLATE (unversioned) → 1.0.0
Rationale: Initial ratification — template placeholders replaced with concrete,
project-specific principles and governance. First versioned constitution.

Principles (initial set, 6 total):
  + I.   Numbers Are Never Invented
  + II.  Discrepancies Must Be Provable, Not Guessed
  + III. One Structured Data Model Is the Source of Truth
  + IV.  Privacy by Default
  + V.   Feature-1 Is the Product
  + VI.  Q&A Answers Are Grounded

Added sections:
  + Core Principles (6 principles)
  + Technology & Data Constraints (Section 2)
  + Development Workflow & Quality Gates (Section 3)
  + Governance

Removed sections: none (template placeholders fully replaced)

Templates requiring updates:
  ✅ .specify/templates/plan-template.md  — Constitution Check gate derives from
     this file dynamically; no hardcoded principle names. No edit required.
  ✅ .specify/templates/spec-template.md  — Generic; no principle references. No edit required.
  ✅ .specify/templates/tasks-template.md — Task categories derive from plan/spec; no edit required.

Follow-up TODOs:
  - Technology stack (mobile framework, OCR/text-layer engine, storage, cloud vs.
    on-device split) is intentionally deferred to the planning phase per the
    user's "Not decided yet" choice. See Technology & Data Constraints.
-->

# Billology Constitution

Billology is a mobile application where users upload images of their bills — grocery,
electricity, mobile recharge, or any other — and the app extracts the data from the
image, checks it for discrepancies, and explains the bill's terms in plain language.

## Core Principles

### I. Numbers Are Never Invented

Every monetary value, date, and quantity shown to the user MUST be extracted
deterministically from the source bill (via OCR or text-layer parsing), not generated,
computed, or restated by an LLM. The LLM's role is to explain and reason about values,
never to produce them. Any figure displayed MUST be traceable to a specific location in
the source document. Arithmetic (sums, tax checks, diffs) is performed in code, not by
the model.

**Rationale**: A bill app that misreports a number is worse than useless — it erodes the
trust the entire product depends on. Determinism and traceability make every displayed
figure auditable.

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

### IV. Privacy by Default

Bills contain sensitive data (account numbers, addresses, consumption patterns). The
system MUST default to processing that minimizes exposure and MUST never transmit more of
a bill than a step requires. Any cloud processing MUST be a deliberate, documented choice,
not a default.

**Rationale**: Users hand over financially and personally sensitive documents. Minimizing
exposure by default is the only posture that earns that trust.

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
  defined under Principle III before any feature consumes the data. Extraction
  (OCR/text-layer parsing) and interpretation (LLM) are separate stages with a clear
  boundary: extraction produces values, interpretation only explains them.
- **Computation in code**: All arithmetic and consistency checks (sums, tax validation,
  duplicate detection, period-over-period diffs) MUST be implemented in deterministic code
  paths, with unit tests, not delegated to an LLM.
- **Traceability**: Each extracted field MUST retain a reference to its location/source in
  the original document so any displayed figure can be traced back.
- **Data minimization**: Each processing step MUST receive only the portion of bill data it
  requires. Cloud calls that transmit bill content MUST be explicitly documented in the
  relevant plan, including what is sent and why.
- **Technology stack — DEFERRED**: The mobile framework, OCR/text-layer engine, storage
  layer, and the cloud-vs-on-device processing split are not yet decided and will be fixed
  during the planning phase (`/speckit-plan`). Plans MUST record these decisions; specs
  MUST remain technology-agnostic.

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

**Version**: 1.0.0 | **Ratified**: 2026-06-09 | **Last Amended**: 2026-06-09

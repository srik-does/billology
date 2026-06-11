# Feature Specification: Bill Capture, Explanation & Discrepancy Pipeline

**Feature Branch**: `001-bill-pipeline`

**Created**: 2026-06-09

**Status**: Draft

**Input**: User description: Billology core — submit a bill (image, PDF, or text), extract its data into one structured record, explain it in plain language, flag provable discrepancies, let the user review/correct and categorize, then surface spending via a dashboard, search, and grounded Q&A.

## Problem Statement

Bills and receipts — utility, telecom, grocery, and more — are cryptic, inconsistent across
vendors, and easy to lose track of. Users struggle to tell what they're being charged for,
whether a charge is wrong, and how their spending accumulates over time. Existing expense apps
track totals but don't explain individual bills or catch billing errors.

## Clarifications

### Session 2026-06-10

- Q: How should the system verify tax math to flag an "incorrect tax calculation" (FR-008) while staying provable from the bill alone? → A: Internal-only — flag a tax error only when the bill states a tax rate and a taxable base and `rate × base ≠ stated tax`; if rate or base is not printed, tax is treated as not verifiable and is not flagged.
- Q: What criteria define a "likely duplicate" bill (FR-020)? → A: Strict — warn only when merchant, bill date, and total amount all match an existing saved bill exactly.
- Q: What happens to a genuine bill from an unsupported vendor/layout (FR-021 vs FR-023)? → A: Best-effort — attempt extraction, mark the record as an unsupported/low-confidence layout, and route it through the normal review-and-correct flow before saving (distinct from the non-bill decline path).
- Q: How does multi-image capture guard against an incorrect merge (out-of-order, overlapping, or two different bills as one)? → A: Both — the system auto-detects likely out-of-order/mismatched/foreign pages and warns, and also surfaces the assembled page sequence in the review step for the user to confirm, reorder, or remove before saving.
- Q: What is the processing-time target for turning a submitted bill into its explained, verified record? → A: ~10 seconds for a typical single-page bill under normal conditions.
- Q: What is the defined, limited set of supported bill types/vendors for the initial version (FR-023)? → A: Telecom/recharge-provider bills and printed grocery receipts; additional types are added in later iterations.

## User Scenarios & Testing *(mandatory)*

Stories are prioritized per the project constitution: the bill-image → explanation +
discrepancy pipeline is the core product (Principle V). P1 stories together constitute the MVP;
P2 stories complete the capture/accuracy/organization experience; P3 stories are the secondary
spending-insight features that read from saved records.

### User Story 3 - Explain a bill (Priority: P1) 🎯 primary

As a user, I want a plain-language explanation of a bill's charges, so that I understand what
I'm paying for without deciphering the layout.

**Why this priority**: Explanation is the core value proposition and the primary reason a user
opens Billology. It is one half of the core pipeline named in the constitution.

**Independent Test**: Submit a processed bill and confirm each charge/line item carries a
plain-language description and every displayed amount/date matches the source exactly.

**Acceptance Scenarios**:

1. **Given** a processed bill, **When** the explanation is shown, **Then** each charge/line item has a plain-language description.
2. **Given** a processed bill, **When** amounts and dates are shown, **Then** every extracted value matches the source bill exactly.

---

### User Story 4 - Detect discrepancies from the bill itself (Priority: P1) 🎯 primary

As a user, I want the app to flag billing errors provable from the bill alone, so that I can
catch overcharges I'd otherwise miss.

**Why this priority**: Catching billing errors is the second half of the core pipeline and the
differentiator from generic expense trackers. Must obey the "provable, not guessed" principle.

**Independent Test**: Process bills with known internal inconsistencies (non-summing total,
duplicate item, wrong tax) and confirm each is flagged with conflicting figures shown; process
clean bills and bills with legitimate non-summing totals and confirm nothing is flagged.

**Acceptance Scenarios**:

1. **Given** a bill whose line items do not sum to the stated total, **When** processed, **Then** the discrepancy is flagged with the conflicting figures shown.
2. **Given** a duplicate line item or incorrect tax calculation, **When** processed, **Then** it is flagged.
3. **Given** a total that doesn't sum for a legitimate reason (rounding, carried-forward balance, deposit), **When** processed, **Then** it is NOT flagged as an error.
4. **Given** no provable inconsistency, **When** processed, **Then** no discrepancy is invented or speculated.
5. **Given** a bill with no itemization (total only), **When** processed, **Then** the system reports that there is nothing to verify rather than erroring or fabricating a check.

---

### User Story 1 - Provide a bill in any common form (Priority: P1)

As a user, I want to submit a bill as a photo, a PDF, or pasted text, so that I can use the app
whether my bill is physical or online.

**Why this priority**: Without ingestion into the single canonical structured representation,
no downstream feature can run. It is the entry point of the core pipeline.

**Independent Test**: Submit the same bill as image, PDF, and text and confirm all three yield
the same structured representation; submit a multi-page PDF and confirm it is treated as one bill.

**Acceptance Scenarios**:

1. **Given** a bill as an image, PDF, or text, **When** I submit it, **Then** the system processes it into the same structured representation regardless of input format.
2. **Given** a multi-page PDF or online bill, **When** submitted, **Then** all pages are processed as one bill.

---

### User Story 5 - Review and correct before saving (Priority: P1)

As a user, I want to review the extracted data and fix anything wrong before it's saved, so that
my records are accurate.

**Why this priority**: Extraction accuracy and traceability are constitutional guarantees
(Principles I–II). Human review before persistence is how the system stays honest about what was
read versus corrected, and it gates the integrity of every downstream feature.

**Independent Test**: Process a bill, confirm extracted fields are shown for review with
low-confidence fields visually marked, edit a field and confirm it is marked user-provided, then
save and confirm the corrected record persists.

**Acceptance Scenarios**:

1. **Given** a processed bill, **When** extraction completes, **Then** the system shows the extracted fields (merchant, date, line items, total, category) for review before saving.
2. **Given** the review screen, **When** a field was extracted with low confidence, **Then** it is visually marked so the user knows what to double-check.
3. **Given** the review screen, **When** I edit a field, **Then** my corrected value replaces the extracted one and is marked as user-provided.
4. **Given** I confirm the review, **When** I save, **Then** the corrected record is persisted.

---

### User Story 2 - Capture physical bills reliably (Priority: P2)

As a user, I want guidance when a photo is unusable or a bill is too long for one image, so that
the system gets a complete, readable capture.

**Why this priority**: Quality capture materially improves extraction accuracy for physical
bills, but the core pipeline can already function for clean images, PDFs, and text without it.

**Independent Test**: Submit a low-light/poor-quality photo and confirm a recapture prompt
instead of a low-confidence record; submit a bill too long for one frame and confirm the system
prompts for additional images and combines them in sequence as one bill.

**Acceptance Scenarios**:

1. **Given** a photo with low light or poor quality, **When** submitted, **Then** the system asks the user to retake it rather than processing a low-confidence image.
2. **Given** a long physical bill, **When** a single image cannot capture it, **Then** the system prompts the user to take additional images and combines them into one logical bill.
3. **Given** multiple captured images, **When** combined, **Then** the system handles them as a single bill in correct sequence.

---

### User Story 6 - Categorize with suggestion and user control (Priority: P2)

As a user, I want the app to suggest a category that I can accept, change, or add to, so that my
bills are organized without losing control over how.

**Why this priority**: Categorization organizes records and feeds the dashboard, but the core
explanation/discrepancy value is deliverable without it.

**Independent Test**: Process a bill, confirm a category is suggested, confirm the user can
accept/change/create a category, and confirm a near-duplicate new category triggers a warning.

**Acceptance Scenarios**:

1. **Given** a processed bill, **When** extraction completes, **Then** the system suggests a category.
2. **Given** a suggested category, **When** I review it, **Then** I can accept it, choose a different existing category, or create a new one.
3. **Given** I create a category similar to an existing one, **When** I add it, **Then** the system warns me of the near-duplicate.

---

### User Story 7 - Supply or adjust the bill date (Priority: P2)

As a user, I want to add or edit the bill's date, so that bills without a printed date (or with a
wrong one) are still recorded correctly.

**Why this priority**: Correct dates matter for time-based views, but a bill can still be
explained and verified without a confirmed date.

**Independent Test**: Process a bill with no detectable date and confirm the user can enter one;
process a bill with a date and confirm the user can override it; confirm user-entered dates are
recorded as user-provided.

**Acceptance Scenarios**:

1. **Given** a bill with no detectable date, **When** reviewing, **Then** the system lets me enter one.
2. **Given** a bill with a detected date, **When** reviewing, **Then** I can still override it.
3. **Given** a user-entered date, **When** saved, **Then** it is recorded as user-provided rather than extracted.

---

### User Story 11 - Avoid duplicate and invalid entries (Priority: P2)

As a user, I want the app to catch when I submit the same bill twice or submit something that
isn't a bill, so that my records stay clean.

**Why this priority**: Protects record quality and prevents fabricated data on non-bill input, a
constitutional must, but is a guard around the pipeline rather than the pipeline itself.

**Independent Test**: Submit a bill already saved and confirm a duplicate warning before saving;
submit a non-bill (e.g. a selfie) and confirm graceful decline without fabricated bill data.

**Acceptance Scenarios**:

1. **Given** a bill matching one already saved, **When** submitted, **Then** the system warns of a likely duplicate before saving.
2. **Given** input that is not a recognizable bill, **When** submitted, **Then** the system declines gracefully instead of fabricating bill data.

---

### User Story 8 - View spending dashboard (Priority: P3)

As a user, I want to see my spending over time broken down by category, so that I understand
where my money goes.

**Why this priority**: Secondary insight feature (constitution Principle V); valuable only once
saved records exist and the core ships complete.

**Independent Test**: With multiple saved bills, open the dashboard and confirm spending is
grouped by category and over time, derived solely from saved records.

**Acceptance Scenarios**:

1. **Given** multiple saved bills, **When** I open the dashboard, **Then** spending is shown grouped by category and over time.
2. **Given** dashboard figures, **When** displayed, **Then** they derive only from saved records.

---

### User Story 9 - Ask questions about spending (Priority: P3)

As a user, I want to ask natural-language questions about my past spending, so that I get answers
without digging through bills.

**Why this priority**: Secondary convenience feature; must be grounded only in stored records
(Principle VI) and is meaningful only with accumulated history.

**Independent Test**: With a history of saved bills, ask "How much did I recharge last time?" and
confirm an answer grounded in records; ask about data not in records and confirm an honest "not
available" rather than an estimate.

**Acceptance Scenarios**:

1. **Given** a history of saved bills, **When** I ask something like "How much did I recharge last time?", **Then** I get an answer grounded in actual records.
2. **Given** a question whose answer isn't in my records, **When** asked, **Then** the system says it doesn't have that information rather than estimating.

---

### User Story 10 - Find a specific bill (Priority: P3)

As a user, I want to search my past bills, so that I can pull up a specific one quickly.

**Why this priority**: Retrieval convenience over saved records; secondary to the core pipeline.

**Independent Test**: With saved bills, search by merchant, category, and date and confirm
matching bills are returned.

**Acceptance Scenarios**:

1. **Given** saved bills, **When** I search by merchant, category, or date, **Then** matching bills are returned.

---

### Edge Cases

- Blurry, skewed, low-light, or faded thermal-receipt photos where extraction confidence is low.
- A bill from an unsupported vendor or layout.
- A bill with no line items (total only), or only total + tax.
- A bill stating a tax amount but no tax rate or taxable base (tax is not verifiable and must not be flagged).
- Totals that legitimately don't sum (rounding, carried-forward balance, deposit).
- The first bill ever processed, with no history (does not affect verification, but affects dashboard/Q&A emptiness).
- A spending question about a period or category with no records.
- Multi-image capture where pages are out of order, overlapping, or two different bills are captured as one.
- A multi-page online PDF.
- Pasted text that is partial, ambiguous, or insufficient to process.
- Indian number formatting (lakh/crore grouping, e.g. ₹1,00,000).
- A near-duplicate category name ("Groceries" vs "Grocery").
- A duplicate bill submitted twice.
- Non-bill input (selfie, unrelated document).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept a bill as an image, PDF, or text and produce a single structured representation from any of them.
- **FR-002**: System MUST process multi-page PDFs and multi-image captures as one logical bill.
- **FR-003**: System MUST extract every monetary value, date, and quantity directly from the source bill; it MUST NOT generate, compute, or restate these via a language model.
- **FR-004**: System MUST tag each stored value as either extracted-from-source or user-provided.
- **FR-005**: System MUST detect low-quality/low-light images and prompt the user to recapture rather than processing them.
- **FR-006**: System MUST prompt for and accept additional images when one image cannot capture an entire physical bill.
- **FR-006a**: When combining multiple images into one logical bill, System MUST auto-detect likely out-of-order, overlapping, or foreign (different-bill) pages and warn the user, AND MUST surface the assembled page sequence in the review step (FR-012) for the user to confirm, reorder, or remove pages before saving.
- **FR-007**: System MUST present a plain-language explanation of each charge.
- **FR-008**: System MUST flag discrepancies provable from the bill alone — line items not summing to total, duplicate charges, or incorrect tax math. Tax math is verified internally only: the system MUST flag a tax error solely when the bill states both a tax rate and a taxable base and `rate × base ≠ stated tax`. When the rate or taxable base is not printed on the bill, tax MUST be treated as not verifiable and MUST NOT be flagged.
- **FR-009**: System MUST NOT flag totals that fail to sum for legitimate reasons (rounding, carried-forward balance, deposits), and MUST NOT flag discrepancies on subjective judgment absent verifiable evidence.
- **FR-010**: System MUST NOT depend on prior-bill history to verify a bill; discrepancy detection rests solely on the current bill's internal consistency.
- **FR-011**: System MUST handle bills with no itemization by reporting nothing to verify, rather than erroring or fabricating.
- **FR-012**: System MUST present extracted fields for user review and correction before saving, and MUST mark low-confidence fields.
- **FR-013**: System MUST suggest a category for each bill and allow the user to accept it, select another, or create a new one.
- **FR-014**: System MUST warn when a newly created category closely matches an existing one.
- **FR-015**: System MUST allow the user to add or override the bill date, recording it as user-provided.
- **FR-016**: System MUST persist one structured record per bill that all features read from; no feature may independently re-parse the raw bill.
- **FR-017**: System MUST display a spending dashboard grouped by category and time, derived solely from saved records.
- **FR-018**: System MUST answer natural-language questions using only saved records, and MUST indicate when an answer is unavailable rather than estimating.
- **FR-019**: System MUST let the user search saved bills by merchant, category, and date.
- **FR-020**: System MUST detect and warn on likely duplicate bills before saving. A bill is treated as a likely duplicate only when its merchant, bill date, and total amount all match an existing saved bill exactly.
- **FR-021**: System MUST detect non-bill input and decline gracefully. A genuine bill from an unsupported vendor or layout is NOT treated as non-bill input: the system MUST attempt best-effort extraction, mark the record as an unsupported/low-confidence layout, and route it through the normal review-and-correct flow (FR-012) before saving.
- **FR-022**: System MUST perform all arithmetic (sums, tax checks) verifiably and traceably to the source bill.
- **FR-023**: System MUST support a defined, limited set of bill types/vendors for the initial version: telecom/recharge-provider bills and printed grocery receipts. Additional bill types are added in later iterations.

### Non-Functional Requirements

- **NFR-Privacy**: System MUST minimize exposure of bill contents during processing; any transmission of bill data beyond the device MUST be a deliberate, documented choice sending no more than a step requires.
- **NFR-Reliability**: Every displayed extracted figure MUST be traceable to a location in the source bill.
- **NFR-Usability**: Explanations MUST be understandable to a non-expert; capture/recapture prompts MUST be clear.
- **NFR-Localization**: System MUST correctly parse Indian number formatting (lakh/crore grouping, e.g. ₹1,00,000).

### Key Entities

- **Bill (canonical record)**: The single structured source of truth for one bill that all features read from. Holds merchant, bill date, totals, taxes, currency, source-format metadata, and the provenance (extracted-from-source vs. user-provided) and confidence of each field, with each extracted figure traceable to a location in the source.
- **Line Item**: An individual charge within a bill — description, quantity, unit amount, line total — each traceable to its source location.
- **Source Artifact**: The original input(s) for a bill — one or more images, a PDF (possibly multi-page), or pasted text — combined into one logical bill in correct sequence.
- **Discrepancy Flag**: A provable inconsistency detected from the bill alone (non-summing total, duplicate item, incorrect tax), carrying the conflicting figures that justify it.
- **Explanation**: Plain-language description attached to the bill and its line items; explains values but never produces them.
- **Category**: A user-controlled label for a bill (suggested, accepted, changed, or created), used for organization and dashboard grouping; near-duplicates are detected.
- **Spending Query**: A natural-language question answered solely from saved records, returning either a record-grounded answer or an explicit "not available."

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can submit a supported bill as image, PDF, or text and receive a correct, understandable explanation.
- **SC-002**: When a supported bill contains a provable inconsistency, the system flags it; when it doesn't (including legitimate non-summing totals), it flags nothing.
- **SC-003**: Every amount and date shown matches the source bill, with user-provided values clearly distinguished from extracted ones.
- **SC-004**: A low-quality photo results in a recapture prompt, not a bad record.
- **SC-005**: A user reviews and can correct extracted data before any bill is saved.
- **SC-006**: Bills are categorized via suggestion with user override, and appear in the dashboard grouped by category and time.
- **SC-007**: A spending question returns an answer consistent with actual records, or an honest "not available."
- **SC-008**: Submitting the same bill twice triggers a duplicate warning; submitting a non-bill is declined gracefully.
- **SC-009**: A typical single-page bill is processed into its explained, verified record within ~10 seconds under normal conditions.

## Assumptions

- **Language & script**: The initial version supports printed bills in English. Handwritten, kirana-style, regional-language, and mixed-script bills are out of scope.
- **Bill type set (FR-023)**: The initial supported set is telecom/recharge-provider bills and printed grocery receipts. Other types (e.g. utility/electricity) are deferred to later iterations.
- **Single user, single device**: One user's records on their own device; no multi-user, family sharing, or cross-device sync in the initial version.
- **Locale**: Indian number formatting and ₹ currency are the primary target; other locales are not guaranteed.
- **No external financial integrations**: The app neither makes payments nor connects to banks/accounts; it works solely from bills the user provides.
- **Processing posture**: Where bill processing happens (on-device vs. cloud) is an architecture decision deferred to planning, constrained by the privacy NFR (minimize exposure; any off-device transmission is deliberate and documented).
- **Confidence scoring**: The extraction step is assumed to produce a per-field confidence signal usable to drive recapture prompts (FR-005) and low-confidence marking (FR-012).

## Out of Scope (initial version)

Payments and transactions; bank or account integrations; multi-user/family sharing; handwritten
or kirana-style receipts; regional-language or mixed-script bills (initial version supports
printed bills in English); and bill types beyond the defined initial set.

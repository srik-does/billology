# Phase 1 Data Model: Bill Pipeline

Single source of truth per Principle III. All monetary fields are `Decimal`/`numeric` (never float).
Every value-bearing field carries **provenance** and a **source trace**. Single user, single device —
no user/tenant table in v1.

## Conventions

- **Provenance** (`provenance` enum): `extracted` | `user_provided`. Required on every figure, date,
  and the merchant/category.
- **Source trace** (`source_ref` JSON): where an extracted value came from — `{artifact_id, page,
  bbox?, line?, raw_text}`. Null only for `user_provided` values. Enforces NFR-Reliability traceability.
- **Confidence** (`confidence` float 0–1, nullable): extraction confidence; drives FR-012 marking.
  Null for `user_provided`.
- Money stored as `numeric(14,2)`; currency default `INR`.

## Entity: Bill (canonical record) — table `bills`

| Field | Type | Notes |
|-------|------|-------|
| `id` | uuid PK | |
| `merchant` | text | with `merchant_provenance`, `merchant_source_ref`, `merchant_confidence` |
| `bill_type` | text enum | `telecom_recharge` \| `grocery` \| `unsupported` (FR-023; unsupported = best-effort layout per FR-021) |
| `bill_date` | date null | with `bill_date_provenance`, `bill_date_source_ref`, `bill_date_confidence`; user may add/override → `user_provided` (FR-015) |
| `currency` | text | default `INR` |
| `subtotal` | numeric(14,2) null | extracted if present |
| `tax_rate` | numeric(6,3) null | extracted; used for tax check only when present |
| `tax_base` | numeric(14,2) null | taxable base; tax check needs both rate+base |
| `tax_amount` | numeric(14,2) null | stated tax |
| `total_amount` | numeric(14,2) | with provenance/source_ref/confidence |
| `category_id` | uuid FK → categories | nullable until review; `category_provenance` records suggested-vs-user |
| `layout_supported` | bool | false ⇒ unsupported/low-confidence layout flag (FR-021) |
| `nothing_to_verify` | bool | true for total-only bills (FR-011) |
| `status` | text enum | `candidate` (pre-review) → `saved` |
| `embedding` | vector(384) | fastembed BAAI/bge-small-en-v1.5; set at save |
| `created_at` / `saved_at` | timestamptz | |

**Relationships**: 1 Bill → N LineItem; 1 Bill → N SourceArtifact; 1 Bill → N DiscrepancyFlag;
1 Bill → 1 Explanation; N Bill → 1 Category.

**Validation / rules**:
- `total_amount` required and `extracted` or `user_provided`.
- A bill is a **duplicate** iff `(merchant, bill_date, total_amount)` exactly equals a `saved` bill (FR-020).
- `embedding` dimension MUST be 384 (matches model). Computed from a text rendering of
  merchant + line-item descriptions + category (no numbers needed for retrieval, but amounts may be
  included as text); generated at save only.
- Tax check eligible iff `tax_rate IS NOT NULL AND tax_base IS NOT NULL` (FR-008 clarify).

## Entity: Line Item — table `line_items`

| Field | Type | Notes |
|-------|------|-------|
| `id` | uuid PK | |
| `bill_id` | uuid FK → bills | cascade |
| `position` | int | order on bill |
| `description` | text | with provenance/source_ref/confidence |
| `quantity` | numeric(12,3) null | |
| `unit_amount` | numeric(14,2) null | |
| `line_total` | numeric(14,2) | with provenance/source_ref/confidence |

**Rule**: `Σ line_total` participates in the sum-vs-total check (deterministic, in code).

## Entity: Source Artifact — table `source_artifacts`

| Field | Type | Notes |
|-------|------|-------|
| `id` | uuid PK | |
| `bill_id` | uuid FK → bills | |
| `kind` | text enum | `image` \| `pdf` \| `text` |
| `storage_path` | text | Supabase Storage (private bucket); null for pasted text |
| `page_order` | int | assembled sequence (FR-002, FR-006a) |
| `raw_text` | text null | extracted text layer / pasted text |
| `quality_score` | float null | from quality_service (FR-005) |

Multiple artifacts combine into one logical bill in confirmed order.

## Entity: Discrepancy Flag — table `discrepancy_flags`

| Field | Type | Notes |
|-------|------|-------|
| `id` | uuid PK | |
| `bill_id` | uuid FK → bills | |
| `kind` | text enum | `sum_mismatch` \| `duplicate_item` \| `tax_mismatch` |
| `conflicting_figures` | jsonb | the figures + their source_refs that justify the flag (Principle II) |
| `explanation_text` | text | plain-language, generated from the figures (no new numbers) |

Only provable flags are stored; legitimate non-summing / unverifiable-tax cases produce **no** row.

## Entity: Explanation — table `explanations`

| Field | Type | Notes |
|-------|------|-------|
| `id` | uuid PK | |
| `bill_id` | uuid FK → bills | |
| `bill_summary` | text | LLM-written from extracted data |
| `line_explanations` | jsonb | `{line_item_id: text}` |

LLM explains values; never produces them. Displayed amounts always read from `line_items`/`bills`.

## Entity: Category — table `categories`

| Field | Type | Notes |
|-------|------|-------|
| `id` | uuid PK | |
| `name` | text unique (case-insensitive) | controlled list |
| `is_seeded` | bool | starter set vs. user-created |

Near-duplicate detection on create: trigram/Levenshtein similarity warning (FR-014). Seed set
includes Telecom/Recharge and Groceries plus a few common categories.

## Entity: Spending Query (transient — not persisted)

Represents a Q&A request routed by `classify_question`:
- **numeric** → `question_to_query` → parameterized SQL over `bills`/`line_items`/`categories` →
  exact aggregates.
- **semantic** → embed question (fastembed) → `embedding <=> query_vec` cosine search → retrieve real
  rows → optional `summarize_results`.
- Unanswerable → explicit "not available" (FR-018, Principle VI). No estimation.

## Indexes & extensions

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;            -- category near-duplicate matching
CREATE INDEX ON bills (merchant, bill_date, total_amount);  -- duplicate detection
CREATE INDEX ON bills (category_id);
CREATE INDEX ON bills (bill_date);                 -- dashboard monthly trend / search
CREATE INDEX ON bills USING hnsw (embedding vector_cosine_ops);  -- semantic Q&A
```

## State transitions

`candidate` (extracted + checked + explained, not persisted)
→ review/edit (user corrects fields, sets provenance, confirms category/date, resolves duplicate warning)
→ `saved` (canonical record persisted, embedding generated).

Non-bill input never creates a `candidate` (declined gracefully, FR-021).

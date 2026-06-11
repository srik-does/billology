# Contract: Dual-path grounded Q&A

Endpoint: `POST /qa`. Schema in [openapi.yaml](./openapi.yaml). Enforces Principle VI / FR-018.

## Routing
`classify_question(question)` → `numeric` | `semantic`.

## Numeric / aggregate path
1. `question_to_query(question, schema)` → **parameterized** SQL restricted to an allowlisted
   schema (`bills`, `line_items`, `categories`) and safe columns.
2. Backend executes the query against Postgres → exact numbers.
3. Response: `{path: numeric, answer, records, executed_query}`. The LLM **never** computes or
   returns the numeric answer — it only writes the query.

Examples: "how much did I recharge last time", "groceries spend in March".

## Semantic / fuzzy path
1. Embed the question locally (`fastembed`, 384-d).
2. `embedding <=> query_vec` cosine search over saved bills → retrieve top real records.
3. Optional `summarize_results(question, retrieved_records)` — summary is over the retrieved real
   rows only; introduces no figures not present in those rows.
4. Response: `{path: semantic, answer, records}`.

Examples: "find the bill where I bought cleaning supplies", "which bills had a late fee".

## Unanswerable
- No matching records / question outside the data → `{path: unanswerable, answer: null}` with an
  explicit "I don't have that information" message. **No estimation** (FR-018).

## Guardrails (testable)
- Generated SQL is parameterized; rejects DML/DDL and non-allowlisted tables/columns.
- Numeric answers equal direct SQL over saved rows.
- Every semantic answer is backed by `records` that actually exist.
- Question about absent data → unanswerable, never a fabricated number.

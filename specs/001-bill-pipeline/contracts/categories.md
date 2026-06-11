# Contract: Categories

Endpoints: `GET /categories`, `POST /categories`. Schemas in [openapi.yaml](./openapi.yaml).

## GET /categories
Returns the controlled list (seeded + user-created). Seed set includes Telecom/Recharge and
Groceries plus a few common categories.

## POST /categories
- Creates a user category. Before insert, runs near-duplicate detection (case-insensitive +
  `pg_trgm` trigram / Levenshtein similarity).
- If a close match exists and `force != true` → `409` with `similar_to` and a warning (FR-014).
- `force: true` overrides and creates anyway.

## Category suggestion (within /bills:process)
`suggest_category(merchant, line_items, known_categories)` returns one of the known names or a
"new category" proposal. The suggestion is validated against the known list before being surfaced;
the user may accept, change, or create (FR-013). The LLM never auto-creates a category.

## Contract tests
- Suggested category is always a member of the known list or an explicit new-suggestion flag.
- Creating "Grocery" when "Groceries" exists → `409` near-duplicate warning.
- `force:true` creates the near-duplicate.

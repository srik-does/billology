# Contract: Dashboard aggregates

Endpoints: `GET /dashboard/by-category`, `GET /dashboard/monthly`. Schemas in [openapi.yaml](./openapi.yaml).

Both derive **solely from saved records** via SQL aggregates (FR-017, Principle III). No LLM involved.

## GET /dashboard/by-category
- `SUM(total_amount) GROUP BY category_id`, optional `bill_date` range filter.
- Feeds the donut/pie view (`react-native-gifted-charts`).

## GET /dashboard/monthly
- `SUM(total_amount) GROUP BY date_trunc('month', bill_date)`, ordered by month.
- Feeds the bar/line trend view.

## Empty state
- No saved bills → empty arrays (mobile shows an empty-state, not an error). First-bill / no-history
  case (spec Edge Cases).

## Contract tests
- Figures equal direct SQL sums over saved rows (no estimation).
- Bills with null `bill_date` excluded from monthly trend (or grouped as "undated" — documented).
- Date-range filter bounds respected.

## What & why

<!-- One or two sentences: what changes, and what problem it solves. -->

## Constitution check

- [ ] No LLM-computed figures: every number shown to a user is extracted from the bill or computed in backend code over `Decimal`s.
- [ ] New/changed extraction paths keep provenance (`extracted` / `user_provided`) and source-line traces intact.
- [ ] Unreadable or non-bill input is declined honestly (no fabricated fields).

## Testing

- [ ] `pytest backend/tests/` passes locally.
- [ ] `ruff check backend/src` and `ruff format --check backend/src` pass.
- [ ] Mobile changes verified in Expo Go / a dev build (if applicable).

## Screenshots (UI changes)

<!-- Before/after for any visible change. Delete if not applicable. -->

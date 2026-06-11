-- Seed the controlled category list (FR-013). Initial supported types are
-- telecom/recharge and grocery; a few common categories are included so the
-- dashboard has sensible buckets from day one.

INSERT INTO categories (name, is_seeded) VALUES
    ('Telecom/Recharge', true),
    ('Groceries', true),
    ('Utilities', true),
    ('Food & Dining', true),
    ('Shopping', true),
    ('Other', true)
ON CONFLICT (lower(name)) DO NOTHING;

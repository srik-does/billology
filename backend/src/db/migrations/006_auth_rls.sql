-- Per-user data isolation (multi-user launch, Constitution Principle IV).
-- Each bill is owned by the Supabase Auth user who created it; Postgres RLS
-- enforces that a user can only ever read/write their own rows. The backend
-- talks to the DB AS the user (anon key + the user's JWT), so auth.uid()
-- resolves to the caller and these policies do the gating in the database —
-- not merely in app code.
--
-- Safe to run on the current (empty) bills table. If bills already held data,
-- user_id would need a backfill before the NOT NULL below.

-- 1) Ownership column -------------------------------------------------------
ALTER TABLE bills
    ADD COLUMN IF NOT EXISTS user_id uuid REFERENCES auth.users (id) ON DELETE CASCADE;

-- New rows default to the calling user, so an insert under the user's JWT is
-- automatically owned correctly (and satisfies the WITH CHECK policy below).
ALTER TABLE bills ALTER COLUMN user_id SET DEFAULT auth.uid();

-- No unowned bills (the table is empty, so this is immediate).
ALTER TABLE bills ALTER COLUMN user_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS bills_user_idx ON bills (user_id);

-- 2) Row-level security -----------------------------------------------------
ALTER TABLE bills ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS bills_select ON bills;
DROP POLICY IF EXISTS bills_insert ON bills;
DROP POLICY IF EXISTS bills_update ON bills;
DROP POLICY IF EXISTS bills_delete ON bills;

CREATE POLICY bills_select ON bills FOR SELECT USING (user_id = auth.uid());
CREATE POLICY bills_insert ON bills FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY bills_update ON bills FOR UPDATE
    USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY bills_delete ON bills FOR DELETE USING (user_id = auth.uid());

-- Child tables inherit ownership through their parent bill. One FOR ALL policy
-- (USING + WITH CHECK) covers select/insert/update/delete.
DO $$
DECLARE
    child text;
BEGIN
    FOREACH child IN ARRAY ARRAY[
        'line_items', 'tax_lines', 'discrepancy_flags', 'explanations', 'source_artifacts'
    ]
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', child);
        EXECUTE format('DROP POLICY IF EXISTS %I_owner ON %I;', child, child);
        EXECUTE format($f$
            CREATE POLICY %I_owner ON %I FOR ALL
            USING (EXISTS (
                SELECT 1 FROM bills b WHERE b.id = %I.bill_id AND b.user_id = auth.uid()
            ))
            WITH CHECK (EXISTS (
                SELECT 1 FROM bills b WHERE b.id = %I.bill_id AND b.user_id = auth.uid()
            ));
        $f$, child, child, child, child);
    END LOOP;
END $$;

-- 3) Categories: a shared, read-only controlled list for every signed-in user.
-- (Seeding/edits happen via the service-role key, which bypasses RLS.)
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS categories_read ON categories;
CREATE POLICY categories_read ON categories FOR SELECT
    USING (auth.role() = 'authenticated');

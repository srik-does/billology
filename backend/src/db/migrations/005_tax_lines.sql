-- Per-component tax breakdown (CGST/SGST/IGST/Cess/VAT/…) for display.
-- The canonical summed figure stays on bills.tax_amount (arithmetic and
-- discrepancy checks read that); these rows are the named breakdown shown
-- after the subtotal in Review and on the saved-bill detail (Principle I:
-- figures come from the bill, validated in code). ``name`` is free text — any
-- tax label the bill prints, not a fixed set.

CREATE TABLE IF NOT EXISTS tax_lines (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    bill_id           uuid NOT NULL REFERENCES bills (id) ON DELETE CASCADE,
    position          int NOT NULL,
    name              text NOT NULL,
    rate              numeric(6,3),
    amount            numeric(14,2) NOT NULL,
    amount_provenance text,
    amount_source_ref jsonb,
    amount_confidence real
);
CREATE INDEX IF NOT EXISTS tax_lines_bill_idx ON tax_lines (bill_id);

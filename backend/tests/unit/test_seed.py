"""Demo seed: corpus shape, internal consistency, and idempotent seeding."""

from __future__ import annotations

from decimal import Decimal

from src.db import seed_demo_bills as seed_mod
from src.services.discrepancy_service import detect


def test_corpus_shape_spans_categories_and_months():
    bills = seed_mod.build_demo_bills()
    assert len(bills) >= 12
    categories = {b.category.name for b in bills}
    assert {"Telecom/Recharge", "Groceries"}.issubset(categories)
    months = {b.bill_date.value[:7] for b in bills}
    assert len(months) >= 4  # spread across the dashboard's monthly trend


def test_every_seeded_bill_is_internally_clean():
    # Seeded bills must not trip discrepancy detection (clean demo corpus).
    for bill in seed_mod.build_demo_bills():
        assert detect(bill) == [], f"{bill.merchant.value} produced flags"


def test_grocery_bills_reconcile():
    for bill in seed_mod.build_demo_bills():
        if bill.bill_type.value != "grocery":
            continue
        items = sum(Decimal(li.line_total.value) for li in bill.line_items)
        assert items == Decimal(bill.subtotal.value)
        assert Decimal(bill.subtotal.value) + Decimal(bill.tax_amount.value) == Decimal(bill.total_amount.value)


class _FakeDB:
    def __init__(self):
        self.bills: list[dict] = []
        self.inserts = 0

    def select(self, table, filters=None):
        if table == "bills" and filters:
            return [b for b in self.bills if b.get("merchant") == filters.get("merchant")]
        if table == "categories":
            return [{"id": "cat", "name": (filters or {}).get("name", "x")}]
        return []

    def insert_row(self, table, row):
        if table == "bills":
            self.inserts += 1
            saved = {"id": f"bill-{self.inserts}", **row}
            self.bills.append(saved)
            return saved
        return {"id": "child"}

    def upload_artifact(self, *a):
        return "path"


def test_seed_is_idempotent():
    db = _FakeDB()
    embed = lambda t: [0.0] * 384

    first = seed_mod.seed(db=db, embed_fn=embed)
    assert first["inserted"] == first["total"]
    assert first["skipped"] == 0

    # Second run: everything already present → all skipped, no new inserts.
    second = seed_mod.seed(db=db, embed_fn=embed)
    assert second["inserted"] == 0
    assert second["skipped"] == second["total"]


def test_dry_run_writes_nothing():
    db = _FakeDB()
    result = seed_mod.seed(db=db, dry_run=True)
    assert db.inserts == 0
    assert result["inserted"] == result["total"]

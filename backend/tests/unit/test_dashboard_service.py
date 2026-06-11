"""Dashboard aggregates: grouping, Decimal sums, date filtering, empty state."""

from __future__ import annotations

from decimal import Decimal

from src.services import dashboard_service as dash


class _FakeDB:
    def __init__(self, bills):
        self._bills = bills
        self._cats = [
            {"id": "c-tel", "name": "Telecom/Recharge"},
            {"id": "c-gro", "name": "Groceries"},
        ]

    def select(self, table, filters=None):
        if table == "categories":
            return self._cats
        if table == "bills":
            return self._bills
        return []


_BILLS = [
    {"total_amount": "239.00", "bill_date": "2026-01-08", "category_id": "c-tel", "status": "saved"},
    {"total_amount": "299.00", "bill_date": "2026-03-09", "category_id": "c-tel", "status": "saved"},
    {"total_amount": "750.00", "bill_date": "2026-03-21", "category_id": "c-gro", "status": "saved"},
    {"total_amount": "770.00", "bill_date": "2026-02-05", "category_id": "c-gro", "status": "saved"},
]


def test_by_category_groups_and_sorts_desc():
    rows = dash.by_category(db=_FakeDB(_BILLS))
    assert rows[0] == {"category": "Groceries", "total": "1520.00"}  # 750 + 770
    assert {"category": "Telecom/Recharge", "total": "538.00"} in rows  # 239 + 299
    # descending by total
    assert Decimal(rows[0]["total"]) >= Decimal(rows[-1]["total"])


def test_monthly_groups_by_month_ascending():
    rows = dash.monthly(db=_FakeDB(_BILLS))
    months = [r["month"] for r in rows]
    assert months == ["2026-01", "2026-02", "2026-03"]
    march = next(r for r in rows if r["month"] == "2026-03")
    assert march["total"] == "1049.00"  # 299 + 750


def test_date_range_filter():
    rows = dash.by_category(db=_FakeDB(_BILLS), date_from="2026-03-01", date_to="2026-03-31")
    # Only the two March bills survive.
    total = sum(Decimal(r["total"]) for r in rows)
    assert total == Decimal("1049.00")


def test_uncategorized_bucket_when_no_category():
    bills = [{"total_amount": "100.00", "bill_date": "2026-04-01", "category_id": None, "status": "saved"}]
    rows = dash.by_category(db=_FakeDB(bills))
    assert rows == [{"category": "Uncategorized", "total": "100.00"}]


def test_empty_when_no_bills():
    assert dash.by_category(db=_FakeDB([])) == []
    assert dash.monthly(db=_FakeDB([])) == []

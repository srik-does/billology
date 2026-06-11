"""Q&A service: numeric computed-from-rows, semantic-from-rows, unanswerable."""

from __future__ import annotations

from decimal import Decimal

from src.services.qa_service import answer_question


class _FakeDB:
    """In-memory stand-in for persistence with categories + bills + match_bills."""

    def __init__(self):
        self.categories = [
            {"id": "c-tel", "name": "Telecom/Recharge"},
            {"id": "c-gro", "name": "Groceries"},
        ]
        self.bills = [
            {"id": "b1", "merchant": "Airtel", "bill_date": "2026-01-08", "total_amount": "239.00", "category_id": "c-tel", "status": "saved"},
            {"id": "b2", "merchant": "Jio", "bill_date": "2026-03-09", "total_amount": "299.00", "category_id": "c-tel", "status": "saved"},
            {"id": "b3", "merchant": "BigBasket", "bill_date": "2026-03-21", "total_amount": "750.00", "category_id": "c-gro", "status": "saved"},
            {"id": "b4", "merchant": "DMart", "bill_date": "2026-02-05", "total_amount": "770.00", "category_id": "c-gro", "status": "saved"},
        ]

    def select(self, table, filters=None):
        if table == "categories":
            return self.categories
        if table == "bills":
            return self.bills
        return []

    def match_bills(self, embedding_literal, match_count=5):
        # Pretend the nearest match is the grocery bill.
        return [self.bills[2]]


def test_numeric_latest_recharge_returns_real_row():
    res = answer_question("How much did I recharge last time?", db=_FakeDB())
    assert res["path"] == "numeric"
    assert "299.00" in res["answer"]  # Jio on 2026-03-09 is the latest telecom
    assert res["records"][0]["merchant"] == "Jio"


def test_numeric_sum_groceries_in_march_equals_row_sum():
    res = answer_question("groceries spend in March", db=_FakeDB())
    assert res["path"] == "numeric"
    # Only BigBasket (750) is in March; DMart (770) is February.
    assert "750.00" in res["answer"]
    assert all(r["category"] == "Groceries" for r in res["records"])


def test_numeric_total_sums_all_bills():
    res = answer_question("how much did I spend in total?", db=_FakeDB())
    total = Decimal("239.00") + Decimal("299.00") + Decimal("750.00") + Decimal("770.00")
    assert str(total) in res["answer"]


def test_unanswerable_when_no_matching_rows():
    res = answer_question("how much did I spend on utilities?", db=_FakeDB())
    assert res["path"] == "unanswerable"
    assert res["records"] == []


def test_semantic_returns_real_retrieved_records():
    res = answer_question(
        "find the bill with vegetables", db=_FakeDB(), embed_fn=lambda q: [0.1] * 384
    )
    assert res["path"] == "semantic"
    assert res["records"][0]["merchant"] == "BigBasket"


def test_semantic_records_carry_resolved_category_not_null():
    # match_bills returns category_id only; the service must resolve the name.
    res = answer_question(
        "find the bill with vegetables", db=_FakeDB(), embed_fn=lambda q: [0.1] * 384
    )
    assert res["records"][0]["category"] == "Groceries"


def test_semantic_unavailable_without_embedder():
    res = answer_question("find the bill with vegetables", db=_FakeDB(), embed_fn=None)
    assert res["path"] == "unanswerable"


def test_blank_question_is_unanswerable():
    assert answer_question("   ", db=_FakeDB())["path"] == "unanswerable"

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

        # Line items for item-level questions: paneer bought twice at one resto.
        self.line_items = [
            {"bill_id": "b3", "description": "Tomatoes 1kg", "line_total": "40.00"},
            {"bill_id": "b3", "description": "Paneer Butter Masala", "line_total": "220.00"},
            {"bill_id": "b4", "description": "Paneer 200g", "line_total": "90.00"},
        ]

    def select(self, table, filters=None):
        if table == "categories":
            return self.categories
        if table == "bills":
            return self.bills
        if table == "line_items":
            return self.line_items
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


# --- Ask reliability: forgiving retrieval ------------------------------------

class _FakeLLM:
    """LLM stub: fixed intent, no summary (exercises the code-side fallbacks)."""

    def __init__(self, intent):
        self._intent = intent

    def derive_intent(self, question, categories, today):
        return self._intent

    def summarize_results(self, question, records):
        raise RuntimeError("no summary in tests")


def _numeric_intent(**overrides):
    intent = {"path": "numeric", "category": None, "month": None,
              "merchant": None, "aggregate": "sum"}
    intent.update(overrides)
    return intent


def test_merchant_match_tolerates_spacing_and_punctuation():
    # 'd mart' must match the saved merchant 'DMart' (the original cliff).
    res = answer_question(
        "how much did I spend at d mart?",
        db=_FakeDB(),
        llm=_FakeLLM(_numeric_intent(merchant="d mart")),
    )
    assert res["path"] == "numeric"
    assert "770.00" in res["answer"]


def test_unmatched_merchant_falls_back_to_semantic_not_cliff():
    res = answer_question(
        "how much did I spend at reliance fresh?",
        db=_FakeDB(),
        embed_fn=lambda q: [0.1] * 384,
        llm=_FakeLLM(_numeric_intent(merchant="reliance fresh")),
    )
    assert res["path"] == "semantic"  # closest matches, not "No bills found"
    assert res["records"]


def test_category_miss_stays_honestly_unanswerable():
    # No Utilities bills exist: the correct answer is "don't have it",
    # not a list of lookalike bills from other categories.
    res = answer_question("how much did I spend on utilities?", db=_FakeDB())
    assert res["path"] == "unanswerable"


def test_keyword_retrieval_works_without_embedder():
    res = answer_question("show me everything from dmart", db=_FakeDB(), embed_fn=None)
    assert res["path"] == "semantic"
    assert any(r["merchant"] == "DMart" for r in res["records"])


def test_tags_make_bills_findable_by_colloquial_words():
    db = _FakeDB()
    db.bills[3]["tags"] = "kirana, d-mart, monthly shopping, staples"
    res = answer_question("kirana purchases", db=db, embed_fn=None)
    assert res["path"] == "semantic"
    assert any(r["merchant"] == "DMart" for r in res["records"])


# --- Item-level spending (aggregate over line items, not whole bills) ---------

def test_item_sum_aggregates_line_totals_not_bill_totals():
    # Paneer was bought twice: 220 (BigBasket) + 90 (DMart) = 310 — NOT the
    # 750 + 770 bill totals (the bug the user reported).
    res = answer_question("how much did I spend on paneer?", db=_FakeDB())
    assert res["path"] == "numeric"
    assert "310.00" in res["answer"]
    assert "750" not in res["answer"] and "770" not in res["answer"]
    # Records carry the item's own amount and name.
    assert {r["item"] for r in res["records"]} == {"Paneer Butter Masala", "Paneer 200g"}


def test_item_sum_respects_merchant_filter():
    res = answer_question(
        "how much did I spend on paneer at bigbasket?",
        db=_FakeDB(),
        llm=_FakeLLM(_numeric_intent(merchant="bigbasket")),
    )
    assert res["path"] == "numeric"
    assert "220.00" in res["answer"]  # only the BigBasket paneer line


def test_item_count_counts_purchases():
    res = answer_question("how many times did I buy paneer?", db=_FakeDB())
    assert res["path"] == "numeric"
    assert "2 time" in res["answer"]


def test_non_item_question_still_bill_level():
    # "groceries" names a category, not a line item, so this stays whole-bill.
    res = answer_question("groceries spend in March", db=_FakeDB())
    assert res["path"] == "numeric"
    assert "750.00" in res["answer"]

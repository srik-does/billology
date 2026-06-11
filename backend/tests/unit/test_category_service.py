"""category_service: known-list resolution and suggestion fallbacks."""

from __future__ import annotations

from src.models import Bill, BillType, LineItem, Provenance, TracedValue
from src.services import category_service


def _tv(v):
    return TracedValue(value=v, provenance=Provenance.extracted)


def _bill(bill_type=BillType.telecom_recharge):
    return Bill(
        merchant=_tv("Airtel"),
        bill_type=bill_type,
        total_amount=_tv("239.00"),
        line_items=[LineItem(position=0, description=_tv("Plan"), line_total=_tv("239.00"))],
    )


class _DBOk:
    def select(self, table, filters=None):
        return [{"name": "Telecom/Recharge"}, {"name": "Groceries"}]


class _DBBoom:
    def select(self, table, filters=None):
        raise RuntimeError("no db")


def test_known_categories_falls_back_when_db_unavailable():
    assert category_service.get_known_categories(db=_DBBoom()) == category_service.SEED_CATEGORIES


def test_suggest_validates_llm_answer_against_known():
    class LLM:
        def suggest_category(self, merchant, items, known):
            return "Telecom/Recharge"

    assert category_service.suggest_category(_bill(), llm=LLM(), db=_DBOk()) == "Telecom/Recharge"


def test_suggest_offlist_answer_falls_back_by_type():
    class LLM:
        def suggest_category(self, merchant, items, known):
            return "Something Random"

    # telecom bill → Telecom/Recharge fallback
    assert category_service.suggest_category(_bill(), llm=LLM(), db=_DBOk()) == "Telecom/Recharge"


def test_suggest_falls_back_when_llm_raises():
    class LLM:
        def suggest_category(self, *a, **k):
            raise RuntimeError("no key")

    assert category_service.suggest_category(_bill(BillType.grocery), llm=LLM(), db=_DBOk()) == "Groceries"

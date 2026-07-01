"""Category suggestion (US6 / FR-013).

Suggests one category from the controlled list. Uses the LLM when available and
validates its answer against the known list; otherwise falls back to a
deterministic mapping by bill type so the review screen always has a suggestion.
Creating brand-new categories is out of the demo scope (no POST /categories).
"""

from __future__ import annotations

from typing import Optional

from src.models import Bill, BillType
from src.services import persistence
from src.services.llm_service import LLMService, get_llm_service

# Mirrors migration 002_seed_categories.sql; used as the offline fallback list.
SEED_CATEGORIES = [
    "Telecom/Recharge",
    "Groceries",
    "Utilities",
    "Food & Dining",
    "Shopping",
    "Other",
]

_BY_TYPE = {
    BillType.telecom_recharge: "Telecom/Recharge",
    BillType.grocery: "Groceries",
}


def get_known_categories(db=persistence) -> list[str]:
    try:
        rows = db.select("categories")
        names = [r["name"] for r in rows if r.get("name")]
        return names or SEED_CATEGORIES
    except Exception:
        return SEED_CATEGORIES


def _fallback(bill: Bill) -> str:
    return _BY_TYPE.get(bill.bill_type, "Other")


def suggest_category(bill: Bill, llm: Optional[LLMService] = None, db=persistence) -> str:
    known = get_known_categories(db)
    try:
        service = llm or get_llm_service()
        line_items = [{"description": li.description.value} for li in bill.line_items]
        answer = service.suggest_category(bill.merchant.value or "", line_items, known)
        if answer in known:
            return answer
        # LLM proposed something off-list (or "new category"); fall back.
        return _fallback(bill) if _fallback(bill) in known else known[-1]
    except Exception:
        return _fallback(bill)

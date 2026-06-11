"""Spending dashboard aggregates (US8 / FR-017).

Both views derive SOLELY from saved records (Principle III) via deterministic
Decimal aggregation — no LLM, no estimation. Optional date-range filtering.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from src.services import persistence


def _to_decimal(v) -> Decimal:
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _saved_bills(db, date_from: Optional[str], date_to: Optional[str]) -> list[dict[str, Any]]:
    cats = {c["id"]: c.get("name") for c in db.select("categories")}
    rows: list[dict[str, Any]] = []
    for b in db.select("bills"):
        if b.get("status") and b["status"] != "saved":
            continue
        bill_date = b.get("bill_date")
        if date_from and (not bill_date or str(bill_date) < date_from):
            continue
        if date_to and (not bill_date or str(bill_date) > date_to):
            continue
        rows.append(
            {
                "total": _to_decimal(b.get("total_amount")),
                "bill_date": bill_date,
                "category": cats.get(b.get("category_id")) or "Uncategorized",
            }
        )
    return rows


def by_category(db=persistence, date_from: Optional[str] = None, date_to: Optional[str] = None) -> list[dict[str, Any]]:
    """Spending grouped by category (donut/pie source), descending by total."""
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for r in _saved_bills(db, date_from, date_to):
        totals[r["category"]] += r["total"]
    items = [{"category": name, "total": str(total)} for name, total in totals.items()]
    items.sort(key=lambda x: Decimal(x["total"]), reverse=True)
    return items


def monthly(db=persistence, date_from: Optional[str] = None, date_to: Optional[str] = None) -> list[dict[str, Any]]:
    """Spending grouped by month YYYY-MM (bar/line trend source), ascending."""
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for r in _saved_bills(db, date_from, date_to):
        bill_date = r["bill_date"]
        month = str(bill_date)[:7] if bill_date else "undated"
        totals[month] += r["total"]
    items = [{"month": m, "total": str(t)} for m, t in totals.items()]
    items.sort(key=lambda x: x["month"])
    return items

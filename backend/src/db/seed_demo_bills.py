"""Seed ~14 realistic saved bills for the dashboard + Q&A demo (T034).

Persists through the shared ``bill_writer`` (same embedding rendering + provenance
as a live save — the C3 acceptance criterion), so seeded and live-saved bills are
indistinguishable to semantic Q&A and dashboard aggregates.

Idempotent: a bill matching an existing (merchant, bill_date, total) is skipped,
so re-running won't duplicate the corpus.

Run (PowerShell, from backend/, with .env configured for Supabase):
    python -m src.db.seed_demo_bills
    python -m src.db.seed_demo_bills --dry-run    # build + validate, no DB writes
"""

from __future__ import annotations

import argparse
from decimal import Decimal
from typing import Callable, Optional

from src.models import (
    Bill,
    BillType,
    Category,
    LineItem,
    Provenance,
    SourceRef,
    TracedValue,
)
from src.services import bill_writer, persistence

# --- builders (pure) --------------------------------------------------------

def _tv(value, line: int = 0) -> TracedValue:
    return TracedValue(
        value=str(value),
        provenance=Provenance.extracted,
        confidence=0.99,
        source_ref=SourceRef(line=line),
    )


def _item(position: int, desc: str, amount) -> LineItem:
    return LineItem(position=position, description=_tv(desc, position), line_total=_tv(amount, position))


def _grocery(merchant: str, date: str, category: str, items: list[tuple[str, str]], rate: str) -> Bill:
    subtotal = sum(Decimal(a) for _, a in items)
    tax = (subtotal * Decimal(rate) / Decimal("100")).quantize(Decimal("0.01"))
    total = subtotal + tax
    return Bill(
        merchant=_tv(merchant),
        bill_type=BillType.grocery,
        bill_date=_tv(date),
        category=Category(name=category),
        line_items=[_item(i, d, a) for i, (d, a) in enumerate(items)],
        subtotal=_tv(subtotal),
        tax_rate=_tv(rate),
        tax_base=_tv(subtotal),
        tax_amount=_tv(tax),
        total_amount=_tv(total),
        status="saved",
    )


def _recharge(merchant: str, date: str, plan: str, amount: str) -> Bill:
    # A recharge is a single inclusive charge → items sum to total, nothing to split.
    return Bill(
        merchant=_tv(merchant),
        bill_type=BillType.telecom_recharge,
        bill_date=_tv(date),
        category=Category(name="Telecom/Recharge"),
        line_items=[_item(0, plan, amount)],
        total_amount=_tv(amount),
        status="saved",
    )


def build_demo_bills() -> list[Bill]:
    """~14 bills across Jan–Jun 2026, multiple categories, for trend + retrieval."""
    return [
        _recharge("Airtel", "2026-01-08", "Unlimited 28-day plan", "239.00"),
        _grocery("BigBasket", "2026-01-22", "Groceries",
                 [("Rice 5kg", "500.00"), ("Cooking Oil 1L", "200.00")], "5"),
        _grocery("DMart", "2026-02-05", "Groceries",
                 [("Atta 10kg", "420.00"), ("Sugar 2kg", "90.00"), ("Tea 500g", "260.00")], "5"),
        _recharge("Jio", "2026-02-10", "Monthly data plan", "299.00"),
        _grocery("More Supermarket", "2026-02-26", "Groceries",
                 [("Milk 6x1L", "330.00"), ("Eggs 30", "210.00")], "0"),
        _grocery("Spencer's", "2026-03-03", "Food & Dining",
                 [("Bakery items", "180.00"), ("Cold cuts", "320.00")], "5"),
        _recharge("Airtel", "2026-03-09", "Unlimited 28-day plan", "239.00"),
        _grocery("BigBasket", "2026-03-21", "Groceries",
                 [("Vegetables", "260.00"), ("Fruits", "340.00"), ("Snacks", "150.00")], "5"),
        _grocery("Reliance Fresh", "2026-04-02", "Groceries",
                 [("Detergent 2kg", "380.00"), ("Soap 6pk", "240.00")], "18"),
        _recharge("Vi", "2026-04-14", "Monthly plan", "359.00"),
        _grocery("Swiggy Instamart", "2026-04-27", "Food & Dining",
                 [("Ready meals", "450.00"), ("Beverages", "180.00")], "5"),
        _grocery("DMart", "2026-05-11", "Groceries",
                 [("Rice 5kg", "510.00"), ("Pulses 2kg", "260.00"), ("Spices", "190.00")], "5"),
        _recharge("Jio", "2026-05-19", "Annual plan installment", "666.00"),
        _grocery("BigBasket", "2026-06-04", "Groceries",
                 [("Household supplies", "620.00"), ("Personal care", "410.00")], "18"),
    ]


# --- IO ---------------------------------------------------------------------

def _already_seeded(db, bill: Bill) -> bool:
    try:
        rows = db.select("bills", {"merchant": bill.merchant.value})
    except Exception:
        return False
    bill_total = bill.total_amount.value
    bill_date = bill.bill_date.value if bill.bill_date is not None else None
    for r in rows:
        same_total = str(r.get("total_amount")) == bill_total or (
            r.get("total_amount") is not None
            and bill_total is not None
            and Decimal(str(r["total_amount"])) == Decimal(bill_total)
        )
        if str(r.get("bill_date")) == bill_date and same_total:
            return True
    return False


def seed(
    *,
    db=persistence,
    embed_fn: Optional[Callable[[str], list[float]]] = None,
    dry_run: bool = False,
) -> dict:
    bills = build_demo_bills()
    inserted = 0
    skipped = 0
    for bill in bills:
        if dry_run:
            inserted += 1
            continue
        if _already_seeded(db, bill):
            skipped += 1
            continue
        kwargs = {"db": db}
        if embed_fn is not None:
            kwargs["embed_fn"] = embed_fn
        bill_writer.save_bill(bill, **kwargs)
        inserted += 1
    return {"total": len(bills), "inserted": inserted, "skipped": skipped}


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo bills for Billology.")
    parser.add_argument("--dry-run", action="store_true", help="Build + validate only; no DB writes.")
    args = parser.parse_args()
    result = seed(dry_run=args.dry_run)
    mode = "DRY RUN" if args.dry_run else "SEED"
    print(f"[{mode}] total={result['total']} inserted={result['inserted']} skipped={result['skipped']}")


if __name__ == "__main__":
    main()

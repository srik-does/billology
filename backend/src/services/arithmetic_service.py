"""Deterministic arithmetic over a Bill candidate (Principle I, FR-022).

Every computation here runs in code on exact ``Decimal`` values pulled straight
from the extracted figures — never via an LLM and never via float. Each result
is traceable back to the source figures that produced it.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

from src.models import Bill, TracedValue


def to_decimal(traced: Optional[TracedValue]) -> Optional[Decimal]:
    """Parse a TracedValue's stored string into an exact Decimal, or None."""
    if traced is None or traced.value is None:
        return None
    try:
        return Decimal(str(traced.value))
    except (InvalidOperation, ValueError):
        return None


def sum_line_items(bill: Bill) -> Decimal:
    """Exact sum of every line item's total."""
    total = Decimal("0")
    for item in bill.line_items:
        amount = to_decimal(item.line_total)
        if amount is not None:
            total += amount
    return total


def expected_tax(bill: Bill) -> Optional[Decimal]:
    """Return rate% × base when both are present, else None (not verifiable)."""
    rate = to_decimal(bill.tax_rate)
    base = to_decimal(bill.tax_base)
    if rate is None or base is None:
        return None
    return (rate / Decimal("100")) * base

"""Deterministic arithmetic over a Bill candidate (Principle I, FR-022).

Every computation here runs in code on exact ``Decimal`` values pulled straight
from the extracted figures — never via an LLM and never via float. Each result
is traceable back to the source figures that produced it.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

from src.models import Bill, Provenance, SourceRef, TaxLine, TracedValue


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


def derive_tax_if_missing(bill: Bill) -> None:
    """Fill an unrecognized tax as ``total − subtotal`` (exact code arithmetic).

    When a bill prints a subtotal and total but the tax line wasn't recognized,
    the gap between them is, on a normal bill, the tax. Recovering it in code
    (Principle I — arithmetic over two printed figures, never the LLM) both
    surfaces the tax for review and prevents a false "subtotal + 0 ≠ total"
    discrepancy on a bill that actually reconciles.

    Guards keep it conservative and honest:

    * only when no tax amount was extracted;
    * only when the gap is positive and no larger than the subtotal (a sane tax
      band — a larger gap is more likely a fee/adjustment than tax);
    * never when rate × base is already verifiable (``expected_tax``), so a
      derived figure can't manufacture a tax-mismatch against a printed rate;
    * the derived value inherits the weaker of the subtotal/total confidences,
      so an uncertain read stays uncertain through the discrepancy gate.

    Mutates ``bill`` in place. A genuine item-vs-subtotal mismatch is unaffected:
    that check is independent and still fires.
    """
    if bill.tax_amount is not None and bill.tax_amount.value is not None:
        return
    if expected_tax(bill) is not None:
        return
    subtotal = to_decimal(bill.subtotal)
    total = to_decimal(bill.total_amount)
    if subtotal is None or total is None:
        return
    gap = total - subtotal
    if gap <= 0 or gap > subtotal:
        return

    confidences = [
        t.confidence
        for t in (bill.subtotal, bill.total_amount)
        if t is not None and t.confidence is not None
    ]
    derived = TracedValue(
        value=format(gap, "f"),
        provenance=Provenance.extracted,
        confidence=min(confidences) if confidences else None,
        source_ref=SourceRef(raw_text="derived in code: total − subtotal"),
    )
    bill.tax_amount = derived
    if not bill.tax_lines:
        bill.tax_lines = [TaxLine(name="Tax", rate=bill.tax_rate, amount=derived)]

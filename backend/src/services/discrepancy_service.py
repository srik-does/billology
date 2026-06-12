"""Provable discrepancy detection (Principle II, FR-008–FR-011).

Flags rest ONLY on the bill's own internal consistency — never prior history,
never model intuition. Every flag carries the conflicting figures that justify
it. Legitimate non-summing reasons (rounding within epsilon, adjustments carried
as line items) and unverifiable tax are deliberately NOT flagged.

Three checks:
  * sum_mismatch  — line items don't sum to the stated subtotal (or, absent a
                    subtotal, items + tax don't sum to the total).
  * duplicate_item — the same description+amount charged more than once.
  * tax_mismatch  — rate% × taxable base ≠ stated tax (only when both printed).

Confidence gate: an arithmetic conflict can only be *proven* if the figures it
rests on were read reliably. When any contributing figure is a low-confidence
OCR read, the flag is still surfaced but marked ``verified=False`` ("couldn't
confirm — please check") rather than asserted as a confirmed discrepancy — this
is what stops a correctly-totalled bill from showing a red error purely because
the scan mis-read a digit. Figures with no confidence (user-provided after
review, pasted text, or a PDF text layer) are trusted.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Optional

from src.models import Bill, DiscrepancyFlag, DiscrepancyKind, LineItem, TracedValue
from src.services.arithmetic_service import (
    expected_tax,
    sum_line_items,
    to_decimal,
)

# Absorbs printed rounding / round-off so it is never mistaken for an error.
EPSILON = Decimal("1.00")

# A figure read by OCR below this confidence is too unreliable to *prove* an
# arithmetic error from (Principle II). Good receipt reads score well above this
# (RapidOCR amount tokens benchmark ~0.9); a sub-threshold figure is genuinely
# shaky, so a conflict involving it is downgraded to "couldn't confirm" instead
# of being asserted. Figures with confidence=None are trusted (see module docs).
MIN_VERIFY_CONFIDENCE = 0.6

_UNVERIFIED_PREFIX = (
    "Some of these figures were read from the scan with low confidence, so this "
    "couldn't be confirmed — please check the highlighted values. "
)


def _fig(name: str, value) -> dict:
    return {name: (str(value) if value is not None else None)}


def _confident(*figures: Optional[TracedValue]) -> bool:
    """True unless some contributing figure has an explicit low confidence.

    A figure with no confidence (None) is trusted — that covers user-provided
    values, pasted text, and PDF text-layer reads. Only an OCR confidence below
    the threshold makes a figure too unreliable to base a proven flag on.
    """
    for traced in figures:
        if traced is None:
            continue
        conf = traced.confidence
        if conf is not None and conf < MIN_VERIFY_CONFIDENCE:
            return False
    return True


def _flag(
    kind: DiscrepancyKind,
    figures: dict,
    proven_text: str,
    contributors: list[Optional[TracedValue]],
) -> DiscrepancyFlag:
    """Build a flag, marking it unverified (with a softened message) when any
    figure it depends on was a low-confidence read."""
    verified = _confident(*contributors)
    text = proven_text if verified else _UNVERIFIED_PREFIX + proven_text
    return DiscrepancyFlag(
        kind=kind,
        conflicting_figures=figures,
        explanation_text=text,
        verified=verified,
    )


def detect(bill: Bill) -> list[DiscrepancyFlag]:
    if bill.nothing_to_verify:
        return []

    flags: list[DiscrepancyFlag] = []
    _check_sum(bill, flags)
    _check_duplicates(bill, flags)
    _check_tax(bill, flags)
    return flags


def _check_sum(bill: Bill, flags: list[DiscrepancyFlag]) -> None:
    if not bill.line_items:
        return  # nothing itemized to verify against

    items_sum = sum_line_items(bill)
    subtotal = to_decimal(bill.subtotal)
    total = to_decimal(bill.total_amount)
    tax = to_decimal(bill.tax_amount) or Decimal("0")
    line_totals = [item.line_total for item in bill.line_items]

    # Bills legitimately reconcile in different ways: items ≈ subtotal,
    # items + tax ≈ total, or items ≈ total (tax-inclusive prices, or amount
    # columns already net of per-item discounts). Only when NO hypothesis
    # holds is the itemization provably inconsistent (Principle II: legitimate
    # non-summing reasons are deliberately not flagged).
    sub_ok = subtotal is not None and abs(items_sum - subtotal) <= EPSILON
    total_ok = total is not None and (
        abs(items_sum + tax - total) <= EPSILON or abs(items_sum - total) <= EPSILON
    )

    if not sub_ok and not total_ok:
        if subtotal is not None:
            flags.append(
                _flag(
                    DiscrepancyKind.sum_mismatch,
                    {
                        **_fig("line_items_sum", items_sum),
                        **_fig("stated_subtotal", subtotal),
                        "difference": str(items_sum - subtotal),
                    },
                    (
                        f"The line items add up to {items_sum}, but the bill states a "
                        f"subtotal of {subtotal}."
                    ),
                    [bill.subtotal, *line_totals],
                )
            )
        elif total is not None:
            expected_total = items_sum + tax
            flags.append(
                _flag(
                    DiscrepancyKind.sum_mismatch,
                    {
                        **_fig("line_items_sum", items_sum),
                        **_fig("tax", tax),
                        **_fig("expected_total", expected_total),
                        **_fig("stated_total", total),
                        "difference": str(expected_total - total),
                    },
                    (
                        f"The line items ({items_sum}) plus tax ({tax}) come to "
                        f"{expected_total}, but the stated total is {total}."
                    ),
                    [bill.total_amount, bill.tax_amount, *line_totals],
                )
            )
        return

    # The itemization verifies against the subtotal — the total itself may still
    # be misprinted, which only this chain can prove.
    if sub_ok and total is not None and not total_ok:
        expected_total = subtotal + tax
        if abs(expected_total - total) > EPSILON:
            flags.append(
                _flag(
                    DiscrepancyKind.sum_mismatch,
                    {
                        **_fig("stated_subtotal", subtotal),
                        **_fig("tax", tax),
                        **_fig("expected_total", expected_total),
                        **_fig("stated_total", total),
                        "difference": str(expected_total - total),
                    },
                    (
                        f"The subtotal ({subtotal}) plus tax ({tax}) come to "
                        f"{expected_total}, but the stated total is {total}."
                    ),
                    [bill.subtotal, bill.tax_amount, bill.total_amount],
                )
            )


def _check_duplicates(bill: Bill, flags: list[DiscrepancyFlag]) -> None:
    groups: dict[tuple[str, str], list[LineItem]] = defaultdict(list)
    for item in bill.line_items:
        desc = (item.description.value or "").strip().lower()
        amount = to_decimal(item.line_total)
        if not desc or amount is None:
            continue
        groups[(desc, str(amount))].append(item)

    for (desc, amount), items in groups.items():
        if len(items) > 1:
            # A "duplicate" read off a low-confidence scan may just be the same
            # line mis-read twice — gate on the figures/descriptions involved.
            contributors: list[Optional[TracedValue]] = []
            for item in items:
                contributors.append(item.line_total)
                contributors.append(item.description)
            flags.append(
                _flag(
                    DiscrepancyKind.duplicate_item,
                    {
                        "description": desc,
                        "amount": amount,
                        "occurrences": len(items),
                    },
                    (
                        f"'{desc}' at {amount} appears {len(items)} times — it may have been "
                        f"charged more than once."
                    ),
                    contributors,
                )
            )


def _check_tax(bill: Bill, flags: list[DiscrepancyFlag]) -> None:
    stated_tax = to_decimal(bill.tax_amount)
    expected = expected_tax(bill)
    # Verifiable only when rate, base, and a stated tax amount are all present.
    if stated_tax is None or expected is None:
        return
    if abs(expected - stated_tax) > EPSILON:
        flags.append(
            _flag(
                DiscrepancyKind.tax_mismatch,
                {
                    **_fig("tax_rate_pct", to_decimal(bill.tax_rate)),
                    **_fig("taxable_base", to_decimal(bill.tax_base)),
                    **_fig("expected_tax", expected),
                    **_fig("stated_tax", stated_tax),
                    "difference": str(expected - stated_tax),
                },
                (
                    f"At {to_decimal(bill.tax_rate)}% on a base of "
                    f"{to_decimal(bill.tax_base)}, tax should be {expected}, but the bill "
                    f"states {stated_tax}."
                ),
                [bill.tax_rate, bill.tax_base, bill.tax_amount],
            )
        )

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
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from typing import Optional

from src.models import Bill, DiscrepancyFlag, DiscrepancyKind
from src.services.arithmetic_service import (
    expected_tax,
    sum_line_items,
    to_decimal,
)

# Absorbs printed rounding / round-off so it is never mistaken for an error.
EPSILON = Decimal("1.00")


def _fig(name: str, value) -> dict:
    return {name: (str(value) if value is not None else None)}


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
                DiscrepancyFlag(
                    kind=DiscrepancyKind.sum_mismatch,
                    conflicting_figures={
                        **_fig("line_items_sum", items_sum),
                        **_fig("stated_subtotal", subtotal),
                        "difference": str(items_sum - subtotal),
                    },
                    explanation_text=(
                        f"The line items add up to {items_sum}, but the bill states a "
                        f"subtotal of {subtotal}."
                    ),
                )
            )
        elif total is not None:
            expected_total = items_sum + tax
            flags.append(
                DiscrepancyFlag(
                    kind=DiscrepancyKind.sum_mismatch,
                    conflicting_figures={
                        **_fig("line_items_sum", items_sum),
                        **_fig("tax", tax),
                        **_fig("expected_total", expected_total),
                        **_fig("stated_total", total),
                        "difference": str(expected_total - total),
                    },
                    explanation_text=(
                        f"The line items ({items_sum}) plus tax ({tax}) come to "
                        f"{expected_total}, but the stated total is {total}."
                    ),
                )
            )
        return

    # The itemization verifies against the subtotal — the total itself may still
    # be misprinted, which only this chain can prove.
    if sub_ok and total is not None and not total_ok:
        expected_total = subtotal + tax
        if abs(expected_total - total) > EPSILON:
            flags.append(
                DiscrepancyFlag(
                    kind=DiscrepancyKind.sum_mismatch,
                    conflicting_figures={
                        **_fig("stated_subtotal", subtotal),
                        **_fig("tax", tax),
                        **_fig("expected_total", expected_total),
                        **_fig("stated_total", total),
                        "difference": str(expected_total - total),
                    },
                    explanation_text=(
                        f"The subtotal ({subtotal}) plus tax ({tax}) come to "
                        f"{expected_total}, but the stated total is {total}."
                    ),
                )
            )


def _check_duplicates(bill: Bill, flags: list[DiscrepancyFlag]) -> None:
    seen: Counter[tuple[str, str]] = Counter()
    for item in bill.line_items:
        desc = (item.description.value or "").strip().lower()
        amount = to_decimal(item.line_total)
        if not desc or amount is None:
            continue
        seen[(desc, str(amount))] += 1

    for (desc, amount), count in seen.items():
        if count > 1:
            flags.append(
                DiscrepancyFlag(
                    kind=DiscrepancyKind.duplicate_item,
                    conflicting_figures={
                        "description": desc,
                        "amount": amount,
                        "occurrences": count,
                    },
                    explanation_text=(
                        f"'{desc}' at {amount} appears {count} times — it may have been "
                        f"charged more than once."
                    ),
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
            DiscrepancyFlag(
                kind=DiscrepancyKind.tax_mismatch,
                conflicting_figures={
                    **_fig("tax_rate_pct", to_decimal(bill.tax_rate)),
                    **_fig("taxable_base", to_decimal(bill.tax_base)),
                    **_fig("expected_tax", expected),
                    **_fig("stated_tax", stated_tax),
                    "difference": str(expected - stated_tax),
                },
                explanation_text=(
                    f"At {to_decimal(bill.tax_rate)}% on a base of "
                    f"{to_decimal(bill.tax_base)}, tax should be {expected}, but the bill "
                    f"states {stated_tax}."
                ),
            )
        )

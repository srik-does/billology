"""LLM-assisted structure labeling, constitution-safe (Principle I).

The LLM sees the extracted lines and labels each line's ROLE (item, total,
tax, payment, junk, ...). It never produces, corrects, or computes a number.
All figures are then re-parsed deterministically (``parse_inr`` via the shared
matchers) from the original extracted lines, carrying the same provenance and
source traces as the heuristic path.

The labeled interpretation is kept ONLY when a code-side reconciliation score
says it is more internally consistent than the keyword-heuristic parse; any
LLM failure (no key, timeout, bad JSON) silently falls back to the heuristic.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from src.models import Bill, LineItem, Provenance, SourceRef, TracedValue
from src.services.extraction.types import ExtractionLine, ExtractionResult
from src.services.parsers.base import (
    _line_item_amount,
    _traced,
    _trailing_amount,
)

logger = logging.getLogger("billology.structure")

# Keep the prompt bounded for very long receipts.
MAX_LINES = 150
EPSILON = Decimal("1.00")


def _dec(tv: Optional[TracedValue]) -> Optional[Decimal]:
    if tv is None:
        return None
    raw = tv.value
    if raw is None or raw == "":
        return None
    try:
        return Decimal(raw)
    except Exception:  # noqa: BLE001
        return None


def _score(bill: Bill) -> tuple[int, int, float]:
    """Deterministic consistency score (higher tuple is better).

    (has a usable nonzero total, items reconcile within epsilon, -|gap|).
    Receipts legitimately reconcile in different ways — items ≈ subtotal,
    items + tax ≈ total, or items ≈ total (tax-inclusive prices / post-discount
    amount columns) — so the gap is the best fit across all hypotheses.
    """
    total = _dec(bill.total_amount)
    has_total = 1 if total else 0
    items = [d for li in bill.line_items if (d := _dec(li.line_total)) is not None]
    if not items:
        return (has_total, 0, 0.0)
    items_sum = sum(items, Decimal(0))
    subtotal = _dec(bill.subtotal)
    tax = _dec(bill.tax_amount) or Decimal(0)
    gaps = []
    if subtotal is not None:
        gaps.append(abs(items_sum - subtotal))
    if total:
        gaps.append(abs(items_sum + tax - total))
        gaps.append(abs(items_sum - total))
    if not gaps:
        return (has_total, 0, 0.0)
    gap = min(gaps)
    return (has_total, 1 if gap <= EPSILON else 0, -float(gap))


def _build_labeled(
    lines: list[ExtractionLine], labels: dict[str, str], heuristic: Bill
) -> Bill:
    """Deterministically re-parse figures from lines, guided only by roles."""
    merchant_ln: Optional[ExtractionLine] = None
    total: Optional[TracedValue] = None
    due: Optional[TracedValue] = None
    subtotal: Optional[TracedValue] = None
    tax_amount: Optional[TracedValue] = None
    line_items: list[LineItem] = []

    for idx, ln in enumerate(lines):
        role = labels.get(str(idx), "junk")
        if role == "merchant" and merchant_ln is None:
            merchant_ln = ln
        elif role == "item":
            item = _line_item_amount(ln.text.rstrip(" |{}"))
            if item:
                amount, description = item
                line_items.append(
                    LineItem(
                        position=len(line_items),
                        description=TracedValue(
                            value=description,
                            provenance=Provenance.extracted,
                            confidence=ln.confidence,
                            source_ref=SourceRef(
                                page=ln.page, line=ln.line, bbox=ln.bbox, raw_text=ln.text
                            ),
                        ),
                        line_total=_traced(amount, ln),
                    )
                )
        elif role in ("total", "due", "subtotal", "tax"):
            parsed = _trailing_amount(ln.text.rstrip(" |{}"))
            if not parsed:
                continue
            traced = _traced(parsed[0], ln)
            if role == "total":
                total = traced
            elif role == "due" and due is None:
                due = traced
            elif role == "subtotal":
                subtotal = traced
            elif role == "tax":
                tax_amount = traced
        # meta/continuation/taxtable/discount/payment/junk: carry no figures.

    merchant = heuristic.merchant
    if merchant_ln is not None:
        merchant = TracedValue(
            value=merchant_ln.text,
            provenance=Provenance.extracted,
            confidence=merchant_ln.confidence,
            source_ref=SourceRef(
                page=merchant_ln.page, line=merchant_ln.line, raw_text=merchant_ln.text
            ),
        )

    final_total = total or due or heuristic.total_amount
    return Bill(
        merchant=merchant,
        bill_type=heuristic.bill_type,
        total_amount=final_total,
        subtotal=subtotal,
        tax_amount=tax_amount,
        tax_rate=heuristic.tax_rate,
        tax_base=heuristic.tax_base,
        line_items=line_items,
        nothing_to_verify=(final_total.value is not None and not line_items),
        layout_supported=heuristic.layout_supported,
        status="candidate",
    )


def refine(result: ExtractionResult, heuristic: Bill) -> Bill:
    """Return the labeled parse when provably more consistent, else heuristic."""
    lines = result.lines[:MAX_LINES]
    if not lines:
        return heuristic
    h_score = _score(heuristic)
    if h_score[0] == 1 and h_score[1] == 1:
        return heuristic  # already internally consistent — nothing to improve
    try:
        from src.services.llm_service import get_llm_service

        payload = [{"i": idx, "text": ln.text} for idx, ln in enumerate(lines)]
        labels = get_llm_service().label_lines(payload)
    except Exception as exc:  # noqa: BLE001 - LLM optional; heuristic is the floor
        logger.warning("structure labeling unavailable, using heuristic: %s", exc)
        return heuristic
    if not labels:
        return heuristic
    try:
        labeled = _build_labeled(lines, labels, heuristic)
    except Exception:  # noqa: BLE001
        logger.exception("labeled build failed, using heuristic")
        return heuristic

    l_score = _score(labeled)
    if l_score > h_score:
        logger.info("structure labels accepted (score %s > %s)", l_score, h_score)
        return labeled
    logger.info("structure labels rejected (score %s <= %s)", l_score, h_score)
    return heuristic

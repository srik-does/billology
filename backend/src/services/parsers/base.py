"""Shared deterministic parsing: ExtractionResult → canonical Bill candidate.

This turns recognized lines into a structured candidate. It is deliberately
deterministic and figure-faithful: amounts come straight from the text via
``parse_inr`` (exact Decimal), each tagged ``provenance=extracted`` with a
source trace. No LLM, no invented numbers (Principle I, FR-003/FR-004).

Telecom and grocery parsers share this core and only adjust keyword hints.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Optional

from src.models import (
    Bill,
    BillType,
    LineItem,
    Provenance,
    SourceRef,
    TracedValue,
)
from src.services.extraction.types import ExtractionLine, ExtractionResult
from src.services.parsers.inr import INRParseError, parse_inr

# A money token, optionally prefixed by a currency marker (loose; used only on
# keyword-guarded total/subtotal/tax lines).
_MONEY = re.compile(r"(?:₹|Rs\.?|INR)?\s*\d[\d,]*(?:\.\d{1,2})?", re.IGNORECASE)
# A *charge* amount on a line item: must be at end of line and look like money —
# i.e. carry a currency marker OR a decimal fraction. This prevents phone numbers,
# quantities, validity days, etc. from being mistaken for amounts (which would
# otherwise produce false sum-mismatch flags downstream).
_CHARGE = re.compile(
    r"(?P<cur>₹|Rs\.?|INR)?\s*(?P<num>\d[\d,]*(?:\.\d{1,2})?)\s*$", re.IGNORECASE
)
_RATE = re.compile(r"(\d{1,2}(?:\.\d+)?)\s*%")
# Decimal-bearing money tokens only (used to spot summary-table rows: a line
# like "Total: 19703.40 541.84 541.84 0.00" is a GST-summary row, not the bill
# total — trusting its right-most token would yield the CESS column).
_DECIMAL_MONEY = re.compile(r"\d[\d,]*\.\d{1,2}")
# Lines that carry money but are not purchases: discounts, payment/tender rows,
# tax-summary rows. Word-bounded so "cash" doesn't match "cashew" etc.
_NON_ITEM = re.compile(
    r"\b(discount|payment|tender|edc|cash|card|upi|change|balance|exempted|round\s?off)\b",
    re.IGNORECASE,
)

_TOTAL_KW = ("grand total", "amount payable", "amount due", "net payable", "total payable", "total")
_SUBTOTAL_KW = ("sub total", "subtotal", "taxable value", "taxable amount")
# Per-component GST lines that must be summed (a correct bill splits tax into these).
_TAX_COMPONENT_KW = ("cgst", "sgst", "igst", "utgst")
# Generic tax keywords (used when a bill states a single combined tax line).
_TAX_KW = ("cgst", "sgst", "igst", "utgst", "gst", "vat", "tax")
# Registration-number lines (GSTIN etc.) carry digits but are not tax amounts.
_TAX_ID = re.compile(r"gst\s*i?n|gst\s*no|gstn", re.IGNORECASE)


def _decimal_str(value: Decimal) -> str:
    return format(value, "f")


def _traced(value: Decimal, ln: ExtractionLine) -> TracedValue:
    return TracedValue(
        value=_decimal_str(value),
        provenance=Provenance.extracted,
        confidence=ln.confidence,
        source_ref=SourceRef(page=ln.page, line=ln.line, bbox=ln.bbox, raw_text=ln.text),
    )


def _trailing_amount(text: str) -> Optional[tuple[Decimal, str, str]]:
    """Return (amount, description, raw_token) using the right-most money token.

    Loose matcher for keyword-guarded total/subtotal/tax lines.
    """
    matches = list(_MONEY.finditer(text))
    if not matches:
        return None
    last = matches[-1]
    token = last.group().strip()
    try:
        amount = parse_inr(token)
    except INRParseError:
        return None
    description = (text[: last.start()]).strip(" :-\t")
    return amount, description, token


def _total_rank(amount: Decimal, token: str) -> int:
    """Rank a total candidate: decimal-bearing nonzero > bare-int nonzero > zero.

    Guards against OCR noise like "Total items sold: 10" or "Total: 0.00"
    (a misread tender row) displacing a real "Total Amount 339.67".
    """
    if amount == 0:
        return 0
    return 2 if "." in token else 1


def _line_item_amount(text: str) -> Optional[tuple[Decimal, str]]:
    """Return (amount, description) only when the line ends in a money-like value.

    Requires a currency marker or a decimal fraction so non-monetary trailing
    numbers (phone numbers, quantities, validity days) are not treated as charges.
    """
    match = _CHARGE.search(text)
    if not match:
        return None
    num = match.group("num")
    if not match.group("cur") and "." not in num:
        return None  # bare integer with no currency marker → not a charge
    try:
        amount = parse_inr(match.group())
    except INRParseError:
        return None
    description = (text[: match.start()]).strip(" :-\t")
    if not description:
        return None
    return amount, description


def _has_kw(text: str, keywords: tuple[str, ...]) -> bool:
    # Tolerate common OCR letter substitutions on keyword lines ("Tota!" → "total").
    low = text.lower().replace("!", "l").replace("|", "l")
    return any(kw in low for kw in keywords)


def _is_table_row(text: str) -> bool:
    """True when a line carries 3+ decimal amounts — a summary-table row
    (e.g. GST breakup columns), whose right-most token is not the line's value."""
    return len(_DECIMAL_MONEY.findall(text)) >= 3


def parse(result: ExtractionResult, bill_type: BillType) -> Bill:
    """Build a Bill candidate from an extraction result."""
    lines = result.lines
    merchant_line = next((ln for ln in lines if ln.text), None)

    total: Optional[TracedValue] = None
    subtotal: Optional[TracedValue] = None
    tax_amount: Optional[TracedValue] = None
    tax_rate: Optional[TracedValue] = None
    tax_base: Optional[TracedValue] = None
    line_items: list[LineItem] = []
    position = 0

    # Tax is accumulated across components (CGST + SGST [+ IGST]) so a correctly
    # split GST bill isn't seen as having incomplete tax.
    comp_tax_total = Decimal(0)
    comp_rate_total = Decimal(0)
    comp_count = 0
    first_tax_ln: Optional[ExtractionLine] = None
    generic_tax: Optional[tuple[Decimal, ExtractionLine]] = None
    generic_rate: Optional[Decimal] = None

    total_rank = -1
    for ln in lines:
        is_total = _has_kw(ln.text, _TOTAL_KW)
        is_subtotal = _has_kw(ln.text, _SUBTOTAL_KW)
        is_component = _has_kw(ln.text, _TAX_COMPONENT_KW)
        is_tax = _has_kw(ln.text, _TAX_KW) and not _TAX_ID.search(ln.text)

        # Summary-table rows (GST breakup etc.) must not be read as the bill's
        # total/subtotal/tax, nor become line items.
        if (is_total or is_subtotal or is_component or is_tax) and _is_table_row(ln.text):
            continue

        if is_total and not is_subtotal:
            parsed = _trailing_amount(ln.text)
            if parsed:
                # Best-ranked total wins; within a rank the last line wins
                # (grand total usually appears last).
                rank = _total_rank(parsed[0], parsed[2])
                if rank >= total_rank:
                    total = _traced(parsed[0], ln)
                    total_rank = rank
            continue
        if is_subtotal:
            parsed = _trailing_amount(ln.text)
            if parsed:
                subtotal = _traced(parsed[0], ln)
            continue
        if is_component:
            parsed = _trailing_amount(ln.text)
            rate_match = _RATE.search(ln.text)
            if parsed:
                comp_tax_total += parsed[0]
                comp_count += 1
                first_tax_ln = first_tax_ln or ln
            if rate_match:
                comp_rate_total += Decimal(rate_match.group(1))
            continue
        if is_tax:
            # Generic / combined tax line (e.g. "GST 18%  90.00", "Total Tax  90").
            parsed = _trailing_amount(ln.text)
            if parsed:
                generic_tax = (parsed[0], ln)
                rate_match = _RATE.search(ln.text)
                if rate_match:
                    generic_rate = Decimal(rate_match.group(1))
            continue

        if _NON_ITEM.search(ln.text):
            continue  # discount/payment/tender rows are not purchases

        # Receipt borders OCR as trailing pipes/braces; strip so the trailing
        # amount is still recognized. (Genuine multi-column item rows — qty,
        # MRP, price, total — keep their right-most amount as the line total.)
        item = _line_item_amount(ln.text.rstrip(" |{}"))
        if item:
            amount, description = item
            line_items.append(
                LineItem(
                    position=position,
                    description=TracedValue(
                        value=description,
                        provenance=Provenance.extracted,
                        confidence=ln.confidence,
                        source_ref=SourceRef(page=ln.page, line=ln.line, bbox=ln.bbox, raw_text=ln.text),
                    ),
                    line_total=_traced(amount, ln),
                )
            )
            position += 1

    # Finalize tax: prefer the sum of GST components; otherwise the single line.
    if comp_count > 0 and first_tax_ln is not None:
        tax_amount = _traced(comp_tax_total, first_tax_ln)
        if comp_rate_total > 0:
            tax_rate = TracedValue(
                value=_decimal_str(comp_rate_total),
                provenance=Provenance.extracted,
                confidence=first_tax_ln.confidence,
                source_ref=SourceRef(
                    page=first_tax_ln.page, line=first_tax_ln.line, raw_text=first_tax_ln.text
                ),
            )
    elif generic_tax is not None:
        tax_amount = _traced(generic_tax[0], generic_tax[1])
        if generic_rate is not None and generic_rate > 0:
            tax_rate = TracedValue(
                value=_decimal_str(generic_rate),
                provenance=Provenance.extracted,
                confidence=generic_tax[1].confidence,
                source_ref=SourceRef(
                    page=generic_tax[1].page, line=generic_tax[1].line, raw_text=generic_tax[1].text
                ),
            )

    # If subtotal exists and a tax rate was found but no base, the subtotal is the base.
    if tax_rate is not None and tax_base is None and subtotal is not None:
        tax_base = subtotal

    merchant = TracedValue(
        value=(merchant_line.text if merchant_line else None),
        provenance=Provenance.extracted,
        confidence=(merchant_line.confidence if merchant_line else None),
        source_ref=(
            SourceRef(page=merchant_line.page, line=merchant_line.line, raw_text=merchant_line.text)
            if merchant_line
            else None
        ),
    )

    # A bill with a total but no itemization has nothing to verify (FR-011).
    nothing_to_verify = total is not None and len(line_items) == 0

    return Bill(
        merchant=merchant,
        bill_type=bill_type,
        total_amount=(total or TracedValue(value=None, provenance=Provenance.extracted)),
        subtotal=subtotal,
        tax_amount=tax_amount,
        tax_rate=tax_rate,
        tax_base=tax_base,
        line_items=line_items,
        nothing_to_verify=nothing_to_verify,
        layout_supported=(bill_type != BillType.unsupported),
        status="candidate",
    )

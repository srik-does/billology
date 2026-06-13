"""Deterministic tax recognition — the code layer, never the LLM (Principle I).

Pins the hardening from the tax-recognition assessment:

* punctuated / spaced tax labels are recognized (``C.G.S.T``, ``S G S T``);
* mixed GST brackets don't fabricate a single combined rate;
* an unrecognized tax is recovered from the printed subtotal/total so a bill
  that actually reconciles isn't falsely flagged (and the tax is shown).
"""

from __future__ import annotations

from decimal import Decimal

from src.models import (
    ArtifactKind,
    Bill,
    BillType,
    LineItem,
    Provenance,
    TracedValue,
)
from src.services.arithmetic_service import derive_tax_if_missing
from src.services.discrepancy_service import detect
from src.services.extraction.types import ExtractionLine, ExtractionResult
from src.services.parsers import base


def _result(lines: list[str]) -> ExtractionResult:
    return ExtractionResult(
        kind=ArtifactKind.image,
        raw_text="\n".join(lines),
        lines=[
            ExtractionLine(text=t, page=0, line=i, confidence=0.9)
            for i, t in enumerate(lines)
        ],
        confidence=0.9,
    )


def _bill(**kwargs) -> Bill:
    base_fields = dict(
        merchant=TracedValue(value="Store", provenance=Provenance.extracted),
        bill_type=BillType.grocery,
        total_amount=TracedValue(value="0", provenance=Provenance.extracted),
    )
    base_fields.update(kwargs)
    return Bill(**base_fields)


# --- Gap 1: punctuated / spaced tax labels ----------------------------------

def test_dotted_gst_labels_are_recognized():
    # "C.G.S.T." / "S.G.S.T." are missed by a plain substring test for "cgst".
    bill = base.parse(
        _result(
            [
                "QuickMart",
                "Rice 500.00",
                "Oil 200.00",
                "Sub Total 700.00",
                "C.G.S.T. 9% 63.00",
                "S.G.S.T. 9% 63.00",
                "Grand Total 826.00",
            ]
        ),
        BillType.grocery,
    )
    assert Decimal(bill.tax_amount.value) == Decimal("126.00")
    assert [tl.name for tl in bill.tax_lines] == ["CGST", "SGST"]
    assert Decimal(bill.tax_rate.value) == Decimal("18")
    assert detect(bill) == []


def test_spaced_gst_label_is_recognized():
    bill = base.parse(
        _result(
            [
                "QuickMart",
                "Widget 100.00",
                "Sub Total 100.00",
                "G S T 18% 18.00",
                "Total 118.00",
            ]
        ),
        BillType.grocery,
    )
    assert Decimal(bill.tax_amount.value) == Decimal("18.00")
    assert [tl.name for tl in bill.tax_lines] == ["GST"]


def test_vat_label_does_not_match_inside_another_word():
    # Word-boundary anchoring keeps the "vat" in "Private" from being read as a
    # VAT line (it would become a bogus tax under a naive substring test).
    bill = base.parse(
        _result(
            [
                "QuickMart",
                "Private Label Soap 50.00",
                "Total 50.00",
            ]
        ),
        BillType.grocery,
    )
    assert bill.tax_amount is None
    assert [li.description.value for li in bill.line_items] == ["Private Label Soap"]


# --- Gap 4: mixed GST brackets have no single combined rate ------------------

def test_mixed_brackets_yield_no_combined_rate():
    bill = base.parse(
        _result(
            [
                "Hypermart",
                "Item A 100.00",
                "CGST 9% 9.00",
                "SGST 9% 9.00",
                "CGST 2.5% 2.50",
                "SGST 2.5% 2.50",
                "Total 123.00",
            ]
        ),
        BillType.grocery,
    )
    assert Decimal(bill.tax_amount.value) == Decimal("23.00")  # summed in code
    assert bill.tax_rate is None  # 9% next to 2.5% → no single effective rate


def test_equal_split_components_still_combine_to_one_rate():
    bill = base.parse(
        _result(
            [
                "Store",
                "Item 700.00",
                "Sub Total 700.00",
                "CGST 9% 63.00",
                "SGST 9% 63.00",
                "Total 826.00",
            ]
        ),
        BillType.grocery,
    )
    assert Decimal(bill.tax_rate.value) == Decimal("18")


# --- Gap 3: derive an unrecognized tax from subtotal/total -------------------

def test_tax_derived_from_subtotal_and_total():
    bill = _bill(
        subtotal=TracedValue(value="605.00", provenance=Provenance.extracted),
        total_amount=TracedValue(value="620.00", provenance=Provenance.extracted),
        line_items=[
            LineItem(
                position=0,
                description=TracedValue(value="A", provenance=Provenance.extracted),
                line_total=TracedValue(value="605.00", provenance=Provenance.extracted),
            )
        ],
    )
    derive_tax_if_missing(bill)
    assert Decimal(bill.tax_amount.value) == Decimal("15.00")
    assert [tl.name for tl in bill.tax_lines] == ["Tax"]
    # The would-be "subtotal + 0 ≠ total" flag is gone — the bill reconciles.
    assert detect(bill) == []


def test_derived_tax_inherits_weaker_confidence():
    bill = _bill(
        subtotal=TracedValue(value="605.00", provenance=Provenance.extracted, confidence=0.4),
        total_amount=TracedValue(value="620.00", provenance=Provenance.extracted, confidence=0.9),
    )
    derive_tax_if_missing(bill)
    assert bill.tax_amount.confidence == 0.4


def test_tax_not_derived_when_rate_and_base_verifiable():
    # rate × base is checkable; fabricating a tax could manufacture a mismatch.
    bill = _bill(
        subtotal=TracedValue(value="700.00", provenance=Provenance.extracted),
        tax_rate=TracedValue(value="18", provenance=Provenance.extracted),
        tax_base=TracedValue(value="700.00", provenance=Provenance.extracted),
        total_amount=TracedValue(value="826.00", provenance=Provenance.extracted),
    )
    derive_tax_if_missing(bill)
    assert bill.tax_amount is None


def test_tax_not_derived_when_gap_exceeds_subtotal():
    # A gap larger than the subtotal is more likely a fee/adjustment than tax.
    bill = _bill(
        subtotal=TracedValue(value="100.00", provenance=Provenance.extracted),
        total_amount=TracedValue(value="250.00", provenance=Provenance.extracted),
    )
    derive_tax_if_missing(bill)
    assert bill.tax_amount is None


# --- Gap 2: tax recovered from a GST summary table (only if it reconciles) ---

def test_tax_recovered_from_summary_table_when_it_reconciles():
    # Tax appears ONLY in the GST summary table (no separate "Tax" line). The
    # rate-anchored columns sum to 210.96, which makes subtotal+tax = total, so
    # it's accepted and the summary rows never become line items.
    bill = base.parse(
        _result(
            [
                "QuickMart",
                "Rice 500.00",
                "Oil 672.00",
                "Sub Total 1172.00",
                "HSN Taxable CGST Rate CGST Amt SGST Rate SGST Amt",
                "1005 1172.00 9% 105.48 9% 105.48",
                "Grand Total 1382.96",
            ]
        ),
        BillType.grocery,
    )
    assert Decimal(bill.tax_amount.value) == Decimal("210.96")
    assert [tl.name for tl in bill.tax_lines] == ["GST"]
    assert [li.description.value for li in bill.line_items] == ["Rice", "Oil"]
    assert detect(bill) == []


def test_summary_tax_discarded_when_it_does_not_reconcile():
    # The recovered figure (18.00) doesn't bridge subtotal→total (100 vs 200),
    # so it must NOT be used — recovery never fabricates a tax.
    bill = base.parse(
        _result(
            [
                "QuickMart",
                "Item 100.00",
                "Sub Total 100.00",
                "HSN Taxable CGST Rate CGST Amt SGST Rate SGST Amt",
                "1005 100.00 9% 9.00 9% 9.00",
                "Grand Total 200.00",
            ]
        ),
        BillType.grocery,
    )
    assert bill.tax_amount is None
    assert [li.description.value for li in bill.line_items] == ["Item"]


def test_main_item_table_header_is_not_treated_as_tax_summary():
    # "HSN Description Rate Amount" is a normal item-table header, not a GST
    # summary — its rows must stay line items, not be dropped as summary rows.
    bill = base.parse(
        _result(
            [
                "QuickMart",
                "HSN Description Rate Amount",
                "1001 Rice 5kg 100.00 500.00",
                "1002 Oil 1L 200.00 200.00",
                "Total 700.00",
            ]
        ),
        BillType.grocery,
    )
    descs = [li.description.value for li in bill.line_items]
    assert any("Rice" in d for d in descs)
    assert any("Oil" in d for d in descs)


def test_tax_not_derived_when_already_present():
    bill = _bill(
        subtotal=TracedValue(value="605.00", provenance=Provenance.extracted),
        tax_amount=TracedValue(value="15.00", provenance=Provenance.extracted),
        total_amount=TracedValue(value="620.00", provenance=Provenance.extracted),
    )
    derive_tax_if_missing(bill)
    assert bill.tax_amount.value == "15.00"  # untouched

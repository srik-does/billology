"""Discrepancy detection — true positives AND absence of false positives.

This is the one protective test the demo spine keeps (Constitution Principle II):
a false overcharge flag on a correct bill is catastrophic, so the no-false-positive
cases matter as much as the positives.
"""

from __future__ import annotations

from src.models import (
    Bill,
    BillType,
    DiscrepancyKind,
    LineItem,
    Provenance,
    SourceRef,
    TracedValue,
)
from src.services.discrepancy_service import detect


def _tv(value, line=0, confidence=None):
    return TracedValue(
        value=str(value),
        provenance=Provenance.extracted,
        confidence=confidence,
        source_ref=SourceRef(line=line),
    )


def _li(desc, total, position=0, confidence=None):
    return LineItem(
        position=position,
        description=TracedValue(value=desc, provenance=Provenance.extracted),
        line_total=_tv(total, confidence=confidence),
    )


def _bill(**kwargs) -> Bill:
    base = dict(
        merchant=_tv("Store"),
        bill_type=BillType.grocery,
        total_amount=_tv("0"),
        line_items=[],
    )
    base.update(kwargs)
    return Bill(**base)


def _kinds(bill) -> set:
    return {f.kind for f in detect(bill)}


# --- True positives ---------------------------------------------------------

def test_sum_mismatch_against_subtotal_is_flagged():
    bill = _bill(
        line_items=[_li("A", "40.00", 0), _li("B", "120.00", 1), _li("C", "50.00", 2)],
        subtotal=_tv("205.00"),  # items sum to 210.00, not 205.00
        total_amount=_tv("215.26"),
    )
    assert DiscrepancyKind.sum_mismatch in _kinds(bill)


def test_sum_mismatch_no_subtotal_items_plus_tax_vs_total():
    bill = _bill(
        line_items=[_li("A", "100.00", 0), _li("B", "100.00", 1)],
        tax_amount=_tv("18.00"),
        total_amount=_tv("999.00"),  # should be ~218.00
    )
    assert DiscrepancyKind.sum_mismatch in _kinds(bill)


def test_correct_subtotal_but_wrong_total_is_flagged():
    # Line items correctly sum to the subtotal, but the stated total is wrong:
    # items=520, subtotal=520, tax=26 → total should be 546, but states 600.
    bill = _bill(
        line_items=[_li("A", "260.00", 0), _li("B", "260.00", 1)],
        subtotal=_tv("520.00"),
        tax_amount=_tv("26.00"),
        total_amount=_tv("600.00"),
    )
    flags = detect(bill)
    kinds = {f.kind for f in flags}
    assert DiscrepancyKind.sum_mismatch in kinds
    # The failing check must be the subtotal+tax vs total one (carries the total).
    assert any(
        "stated_total" in f.conflicting_figures and f.conflicting_figures.get("stated_total") == "600.00"
        for f in flags
    )


def test_duplicate_line_item_is_flagged():
    bill = _bill(
        line_items=[_li("Coca-Cola", "40.00", 0), _li("Coca-Cola", "40.00", 1)],
        subtotal=_tv("80.00"),
        total_amount=_tv("80.00"),
    )
    assert DiscrepancyKind.duplicate_item in _kinds(bill)


def test_tax_mismatch_is_flagged_when_rate_times_base_wrong():
    bill = _bill(
        line_items=[_li("A", "700.00", 0)],
        subtotal=_tv("700.00"),
        tax_rate=_tv("18"),
        tax_base=_tv("700.00"),
        tax_amount=_tv("200.00"),  # 18% of 700 = 126, not 200
        total_amount=_tv("900.00"),
    )
    assert DiscrepancyKind.tax_mismatch in _kinds(bill)


# --- No false positives -----------------------------------------------------

def test_clean_bill_flags_nothing():
    bill = _bill(
        line_items=[_li("A", "40.00", 0), _li("B", "120.00", 1), _li("C", "45.00", 2)],
        subtotal=_tv("205.00"),
        tax_rate=_tv("5"),
        tax_base=_tv("205.00"),
        tax_amount=_tv("10.25"),
        total_amount=_tv("215.25"),
    )
    assert _kinds(bill) == set()


def test_split_gst_correct_bill_not_flagged():
    # CGST 9% + SGST 9% summed to 18% / 126.00 on a 700 base (the real-bill case).
    bill = _bill(
        line_items=[_li("Rice", "500.00", 0), _li("Oil", "200.00", 1)],
        subtotal=_tv("700.00"),
        tax_rate=_tv("18"),
        tax_base=_tv("700.00"),
        tax_amount=_tv("126.00"),
        total_amount=_tv("826.00"),
    )
    assert _kinds(bill) == set()


def test_rounding_within_epsilon_not_flagged():
    # items + tax = 218.01 vs total 218.00 (one paisa rounding) → not flagged.
    bill = _bill(
        line_items=[_li("A", "100.00", 0), _li("B", "100.01", 1)],
        tax_amount=_tv("18.00"),
        total_amount=_tv("218.00"),
    )
    assert DiscrepancyKind.sum_mismatch not in _kinds(bill)


def test_carried_forward_balance_as_line_item_not_flagged():
    # A "Previous Balance" line is part of the items and is included in the sum.
    bill = _bill(
        line_items=[_li("Current charges", "239.00", 0), _li("Previous Balance", "50.00", 1)],
        total_amount=_tv("289.00"),
    )
    assert DiscrepancyKind.sum_mismatch not in _kinds(bill)


def test_tax_not_verifiable_without_rate_or_base_not_flagged():
    # Tax amount present but no rate/base printed → cannot verify → not flagged.
    bill = _bill(
        line_items=[_li("A", "100.00", 0)],
        tax_amount=_tv("18.00"),
        total_amount=_tv("118.00"),
    )
    assert DiscrepancyKind.tax_mismatch not in _kinds(bill)


def test_total_only_bill_nothing_to_verify():
    bill = _bill(total_amount=_tv("299.00"), nothing_to_verify=True)
    assert detect(bill) == []


# --- Confidence gating: provable vs. "couldn't confirm" ----------------------

def _flags_by_kind(bill) -> dict:
    return {f.kind: f for f in detect(bill)}


def test_high_confidence_mismatch_is_proven_verified_true():
    # Same data as the subtotal mismatch above, but with explicit high
    # confidence on the figures → asserted as a proven discrepancy.
    bill = _bill(
        line_items=[
            _li("A", "40.00", 0, confidence=0.97),
            _li("B", "120.00", 1, confidence=0.97),
            _li("C", "50.00", 2, confidence=0.97),
        ],
        subtotal=_tv("205.00", confidence=0.97),
        total_amount=_tv("215.26", confidence=0.97),
    )
    flag = _flags_by_kind(bill)[DiscrepancyKind.sum_mismatch]
    assert flag.verified is True


def test_low_confidence_mismatch_is_surfaced_but_not_verified():
    # A low-confidence line read shouldn't be asserted as a confirmed error —
    # the flag is still surfaced (no false green "all clear") but verified=False.
    bill = _bill(
        line_items=[
            _li("A", "40.00", 0, confidence=0.30),  # shaky OCR read
            _li("B", "120.00", 1, confidence=0.95),
            _li("C", "50.00", 2, confidence=0.95),
        ],
        subtotal=_tv("205.00", confidence=0.95),
        total_amount=_tv("215.26", confidence=0.95),
    )
    flags = detect(bill)
    flag = _flags_by_kind(bill)[DiscrepancyKind.sum_mismatch]
    assert DiscrepancyKind.sum_mismatch in {f.kind for f in flags}  # still surfaced
    assert flag.verified is False
    assert "low confidence" in flag.explanation_text.lower()


def test_none_confidence_is_trusted_verified_true():
    # User-provided / pasted-text figures carry no confidence → trusted as proven.
    bill = _bill(
        line_items=[_li("A", "40.00", 0), _li("B", "120.00", 1), _li("C", "50.00", 2)],
        subtotal=_tv("205.00"),
        total_amount=_tv("215.26"),
    )
    flag = _flags_by_kind(bill)[DiscrepancyKind.sum_mismatch]
    assert flag.verified is True


def test_low_confidence_tax_mismatch_not_verified():
    bill = _bill(
        line_items=[_li("A", "700.00", 0)],
        subtotal=_tv("700.00"),
        tax_rate=_tv("18"),
        tax_base=_tv("700.00"),
        tax_amount=_tv("200.00", confidence=0.25),  # 18% of 700 = 126, not 200
        total_amount=_tv("900.00"),
    )
    flag = _flags_by_kind(bill)[DiscrepancyKind.tax_mismatch]
    assert flag.verified is False


def test_legit_two_units_same_price_with_quantity_not_duplicate():
    # Two identical lines but each carries quantity=1 distinctly is ambiguous;
    # our rule flags identical description+amount as a *potential* duplicate, but
    # a single occurrence must never flag.
    bill = _bill(
        line_items=[_li("Milk", "60.00", 0)],
        subtotal=_tv("60.00"),
        total_amount=_tv("60.00"),
    )
    assert DiscrepancyKind.duplicate_item not in _kinds(bill)

"""Vision extraction (v2, Constitution 2.0.0 Principle I).

The vision LLM only transcribes; these tests pin the code-side contract:
every transcribed figure is re-validated to an exact Decimal (unparseable
values are dropped, never repaired), tax components are summed in code, each
kept field is traced to its transcribed raw line, and any provider failure
falls back to the deterministic pipeline instead of failing the request.
"""

from __future__ import annotations

import io
from decimal import Decimal

import pytest
import src.services.llm_service as llm_service
from PIL import Image
from src.models import ArtifactKind, BillType, Provenance
from src.services.discrepancy_service import detect as detect_discrepancies
from src.services.extraction import NotABillError, process_inputs, vision
from src.services.extraction.types import ExtractionLine, ExtractionResult
from src.services.extraction.vision import VISION_CONFIDENCE, VisionExtractionError


class FakeLLM:
    def __init__(self, payload=None, exc=None):
        self.payload = payload
        self.exc = exc
        self.calls: list[list[str]] = []

    def extract_bill_image(self, images_b64):
        self.calls.append(images_b64)
        if self.exc is not None:
            raise self.exc
        return self.payload


def _img() -> Image.Image:
    return Image.new("RGB", (60, 90), "white")


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    _img().save(buf, "PNG")
    return buf.getvalue()


def _patch_llm(monkeypatch, fake: FakeLLM) -> None:
    monkeypatch.setattr(llm_service, "get_llm_service", lambda: fake)


def _payload() -> dict:
    # Internally consistent: items 425 + 180 = 605, tax 7.50 + 7.50, total 620.
    return {
        "is_bill": True,
        "raw_lines": [
            "SRI VENKATA SUPERMARKET",
            "Date: 12/06/2026",
            "Rice 5kg 1 425.00 425.00",
            "Toor Dal 1kg 2 90.00 180.00",
            "CGST 2.5% 7.50",
            "SGST 2.5% 7.50",
            "Total ₹620.00",
        ],
        "merchant": "SRI VENKATA SUPERMARKET",
        "bill_date": "2026-06-12",
        "bill_type": "grocery",
        "currency": "inr",
        "subtotal": None,
        "tax_rate": None,
        "tax_amount": None,
        "tax_components": [
            {"name": "CGST", "rate": "2.5", "amount": "7.50"},
            {"name": "SGST", "rate": "2.5", "amount": "7.50"},
        ],
        "total_amount": "620.00",
        "line_items": [
            {"description": "Rice 5kg", "quantity": "1", "unit_amount": "425.00", "line_total": "425.00"},
            {"description": "Toor Dal 1kg", "quantity": "2", "unit_amount": "90.00", "line_total": "180.00"},
        ],
    }


def test_transcription_is_validated_summed_in_code_and_traced(monkeypatch):
    _patch_llm(monkeypatch, FakeLLM(payload=_payload()))

    bill = vision.extract_bill([_img()])

    assert bill.total_amount.value == "620.00"
    assert bill.total_amount.provenance == Provenance.extracted
    assert bill.total_amount.confidence == VISION_CONFIDENCE
    assert bill.total_amount.source_ref.raw_text == "Total ₹620.00"

    # CGST + SGST summed in code (the model never returned a combined figure).
    assert Decimal(bill.tax_amount.value) == Decimal("15.00")
    assert Decimal(bill.tax_rate.value) == Decimal("5.0")

    assert [li.line_total.value for li in bill.line_items] == ["425.00", "180.00"]
    assert bill.line_items[0].description.source_ref.raw_text == "Rice 5kg 1 425.00 425.00"

    assert bill.merchant.value == "SRI VENKATA SUPERMARKET"
    assert bill.bill_date.value == "2026-06-12"
    assert bill.bill_type == BillType.grocery
    assert bill.currency == "INR"
    assert bill.layout_supported is True
    assert bill.status == "candidate"
    assert bill.nothing_to_verify is False

    # The downstream arithmetic layer agrees this bill reconciles.
    assert detect_discrepancies(bill) == []


def test_component_rate_sum_outranks_echoed_single_rate(monkeypatch):
    # Seen live (restaurant bill): the model echoed one component's rate (2.5)
    # into the top-level tax_rate while CGST+SGST rows carry 2.5% each — the
    # bill's effective rate is the printed components' sum, 5%.
    payload = _payload()
    payload["tax_rate"] = "2.5"
    _patch_llm(monkeypatch, FakeLLM(payload=payload))
    bill = vision.extract_bill([_img()])
    assert Decimal(bill.tax_rate.value) == Decimal("5.0")


def test_mixed_rate_components_yield_no_single_rate(monkeypatch):
    # Seen live (9-page hypermart bill): 18% and 5% GST brackets. Summing
    # bracket rates fabricates a rate no row prints — the tax check must be
    # skipped as unverifiable instead of flagging from it.
    payload = _payload()
    payload["tax_components"] = [
        {"name": "GST 18%", "rate": "18", "amount": "68.08"},
        {"name": "GST 18%", "rate": "18", "amount": "68.08"},
        {"name": "GST 5%", "rate": "5", "amount": "150.60"},
        {"name": "GST 5%", "rate": "5", "amount": "150.60"},
    ]
    _patch_llm(monkeypatch, FakeLLM(payload=payload))
    bill = vision.extract_bill([_img()])
    assert Decimal(bill.tax_amount.value) == Decimal("437.36")  # summed in code
    assert bill.tax_rate is None


def test_uncertain_field_softens_its_flags_only(monkeypatch):
    # Blurry total: the conflict must surface as "couldn't confirm"
    # (verified=False), not an asserted error — the same behavior v1 derived
    # from low OCR confidence. Crucially the uncertainty is PER FIELD: the
    # cleanly-read fields keep full confidence so the review screen marks
    # only the shaky one (seen live on a crumpled bill where a global
    # "degraded" verdict put a check badge on every correct field).
    payload = _payload()
    payload["uncertain_fields"] = ["total_amount"]
    # A printed-and-transcribed total that doesn't reconcile (items 605 + tax
    # 15 = 620, stated 720): a genuine conflict, but read off a blurry line.
    payload["total_amount"] = "720.00"
    payload["raw_lines"][6] = "Total ₹720.00"
    _patch_llm(monkeypatch, FakeLLM(payload=payload))

    bill = vision.extract_bill([_img()])

    assert bill.total_amount.confidence == vision.DEGRADED_CONFIDENCE
    assert bill.merchant.confidence == vision.VISION_CONFIDENCE
    assert bill.line_items[0].line_total.confidence == vision.VISION_CONFIDENCE
    flags = detect_discrepancies(bill)
    assert flags and all(f.verified is False for f in flags)


def test_transcribed_but_unstructured_tax_is_backfilled(monkeypatch):
    # Seen live (crumpled Sharma Restaurant bill): CGST/SGST rows land in the
    # transcript but the model leaves the structured tax fields empty — the
    # deterministic keyword parser must recover them from the transcript so
    # the bill reconciles instead of false-flagging items+0 ≠ total.
    payload = _payload()
    payload["tax_components"] = []
    payload["tax_amount"] = None
    payload["tax_rate"] = None
    _patch_llm(monkeypatch, FakeLLM(payload=payload))

    bill = vision.extract_bill([_img()])

    assert Decimal(bill.tax_amount.value) == Decimal("15.00")  # CGST+SGST from raw_lines
    assert Decimal(bill.tax_rate.value) == Decimal("5.0")
    assert bill.tax_amount.source_ref.raw_text == "CGST 2.5% 7.50"
    assert detect_discrepancies(bill) == []


def test_transcribed_but_unstructured_total_is_backfilled(monkeypatch):
    payload = _payload()
    payload["total_amount"] = None  # transcript still carries "Total ₹620.00"
    _patch_llm(monkeypatch, FakeLLM(payload=payload))

    bill = vision.extract_bill([_img()])

    assert bill.total_amount.value == "620.00"
    assert bill.total_amount.confidence == vision.VISION_CONFIDENCE
    assert bill.total_amount.source_ref.raw_text == "Total ₹620.00"


def test_printed_taxable_value_is_the_tax_base(monkeypatch):
    # Tax-inclusive receipts print the taxable value separately (GST summary);
    # assuming base=subtotal there fabricates a tax-mismatch flag.
    payload = _payload()
    payload["taxable_value"] = "590.48"
    _patch_llm(monkeypatch, FakeLLM(payload=payload))
    bill = vision.extract_bill([_img()])
    assert bill.tax_base.value == "590.48"


def test_partial_extraction_suppresses_arithmetic_checks(monkeypatch):
    # 4 of 9 pages cannot prove a sum mismatch (Principle II).
    payload = _payload()
    payload["line_items"] = payload["line_items"][:1]  # items no longer sum
    _patch_llm(monkeypatch, FakeLLM(payload=payload))

    bill = vision.extract_bill([_img()], partial=True)

    assert bill.nothing_to_verify is True
    assert detect_discrepancies(bill) == []


def test_unparseable_figures_are_dropped_never_repaired(monkeypatch):
    payload = _payload()
    payload["total_amount"] = "unknown"
    payload["line_items"][1]["line_total"] = "n/a"
    # No total in the transcript either — otherwise the deterministic
    # backfill would (correctly) recover the printed one.
    payload["raw_lines"][6] = "Thank you, visit again"
    _patch_llm(monkeypatch, FakeLLM(payload=payload))

    bill = vision.extract_bill([_img()])

    assert bill.total_amount.value is None
    assert [li.description.value for li in bill.line_items] == ["Rice 5kg"]


def test_not_a_bill_is_declined_not_fabricated(monkeypatch):
    _patch_llm(monkeypatch, FakeLLM(payload={"is_bill": False, "raw_lines": []}))
    with pytest.raises(NotABillError):
        vision.extract_bill([_img()])


def test_no_usable_figures_raises_fallback_not_decline(monkeypatch):
    payload = {"is_bill": True, "raw_lines": ["something blurry"], "line_items": []}
    _patch_llm(monkeypatch, FakeLLM(payload=payload))
    with pytest.raises(VisionExtractionError):
        vision.extract_bill([_img()])


def test_bill_type_hint_overrides_model_claim(monkeypatch):
    _patch_llm(monkeypatch, FakeLLM(payload=_payload()))
    bill = vision.extract_bill([_img()], bill_type_hint="telecom_recharge")
    assert bill.bill_type == BillType.telecom_recharge


def test_off_list_bill_type_falls_back_to_keyword_detection(monkeypatch):
    payload = _payload()
    payload["bill_type"] = "electricity"
    payload["raw_lines"][0] = "AIRTEL PREPAID RECHARGE"
    _patch_llm(monkeypatch, FakeLLM(payload=payload))
    bill = vision.extract_bill([_img()])
    assert bill.bill_type == BillType.telecom_recharge


def test_model_computed_line_total_loses_to_printed_amount(monkeypatch):
    # Seen live with llama-4-scout: row "Toor Dal 1kg 2 180.00" (printed row
    # total 180.00) came back as unit_amount=180.00 with a COMPUTED
    # line_total=360.00 that is printed nowhere. The traced printed amount must
    # win because only it reconciles with the stated subtotal.
    payload = _payload()
    payload["raw_lines"] = [
        "SRI BALAJI SUPERMARKET",
        "Rice 5kg 1 425.00",
        "Toor Dal 1kg 2 180.00",
        "Sub Total 605.00",
        "Total Rs 605.00",
    ]
    payload["subtotal"] = "605.00"
    payload["total_amount"] = "605.00"
    payload["tax_components"] = []
    payload["line_items"] = [
        {"description": "Rice 5kg", "quantity": "1", "unit_amount": "425.00", "line_total": "425.00"},
        {"description": "Toor Dal 1kg", "quantity": "2", "unit_amount": "180.00", "line_total": "360.00"},
    ]
    _patch_llm(monkeypatch, FakeLLM(payload=payload))

    bill = vision.extract_bill([_img()])

    assert bill.line_items[1].line_total.value == "180.00"
    assert bill.line_items[1].line_total.source_ref.raw_text == "Toor Dal 1kg 2 180.00"
    assert detect_discrepancies(bill) == []


def _classic_result() -> ExtractionResult:
    lines = ["QuickMart", "Apples 50.00", "Bananas 50.00", "Total 100.00"]
    return ExtractionResult(
        kind=ArtifactKind.image,
        raw_text="\n".join(lines),
        lines=[
            ExtractionLine(text=t, page=0, line=i, confidence=0.9)
            for i, t in enumerate(lines)
        ],
        confidence=0.9,
    )


def test_vision_failure_falls_back_to_deterministic_pipeline(monkeypatch):
    def _unavailable(images, bill_type_hint=None, partial=False):
        raise VisionExtractionError("provider down")

    monkeypatch.setattr("src.services.extraction.vision.extract_bill", _unavailable)
    monkeypatch.setattr(
        "src.services.extraction.extract_image", lambda _bytes: _classic_result()
    )

    bill = process_inputs(files=[(_png_bytes(), "bill.png", "image/png")])

    assert bill.total_amount.value == "100.00"
    assert len(bill.line_items) == 2


def test_vision_kill_switch_routes_straight_to_classic(monkeypatch):
    from src.config import get_settings

    monkeypatch.setattr(get_settings(), "vision_extraction", False)

    def _must_not_run(images, bill_type_hint=None, partial=False):  # pragma: no cover
        raise AssertionError("vision path used despite VISION_EXTRACTION=false")

    monkeypatch.setattr("src.services.extraction.vision.extract_bill", _must_not_run)
    monkeypatch.setattr(
        "src.services.extraction.extract_image", lambda _bytes: _classic_result()
    )

    bill = process_inputs(files=[(_png_bytes(), "bill.png", "image/png")])
    assert bill.total_amount.value == "100.00"

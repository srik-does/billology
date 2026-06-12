"""Vision-LLM bill extraction — the v2 primary path for image bills.

A multimodal LLM transcribes the photographed bill (Constitution v2.0.0,
Principle I): it may only copy what is printed, never compute or invent a
value. Its output is treated as untrusted text — every figure is re-validated
here in code (``parse_inr`` → exact ``Decimal``; values that fail validation
are dropped, never repaired), tax components are summed in code, and each kept
field carries the same ``TracedValue`` provenance as the deterministic path,
pointing at the transcribed raw line it came from. Arithmetic and discrepancy
checks downstream are unchanged.

Honesty gates mirroring the v1 confidence semantics (Principle II):

* The model self-reports ``legibility``; a degraded read carries a confidence
  below the discrepancy gate, so flags built on it say "couldn't confirm"
  instead of asserting a proven error.
* A known-partial extraction (pages dropped by the cap) sets
  ``nothing_to_verify`` — a subset of pages cannot *prove* a sum mismatch.

Any provider failure (no key, timeout, malformed JSON) raises
``VisionExtractionError`` so the orchestrator falls back to the deterministic
OCR pipeline; a confident "this is not a bill" from the model is a decline
(``NotABillError``), not a fallback.
"""

from __future__ import annotations

import base64
import io
import logging
import re
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from src.models import Bill, BillType, LineItem, Provenance, SourceRef, TracedValue
from src.services.parsers import detect_bill_type
from src.services.parsers.inr import INRParseError, parse_inr

from .types import NotABillError

logger = logging.getLogger("billology.vision")

# Vision transcription is high-trust (it reads layouts OCR garbles) but not
# infallible, so figures carry an explicit confidence rather than the implicit
# trust (None) reserved for text layers and user-corrected values. Above the
# discrepancy gate's MIN_VERIFY_CONFIDENCE, so proven flags stay proven.
VISION_CONFIDENCE = 0.9
# When the model itself reports the bill as hard to read, figures drop below
# the verify gate (0.6): conflicts surface as "couldn't confirm", not asserted.
DEGRADED_CONFIDENCE = 0.5

# Long side cap before JPEG re-encode: keeps the base64 payload well under
# provider limits while preserving digit-level detail on receipt photos.
MAX_IMAGE_DIM = 2048
_JPEG_QUALITY = 88

# Groq's llama-4 vision endpoint accepts at most 5 images per request.
MAX_IMAGES = 5

# Defensive caps on model output so a runaway response can't bloat the bill.
MAX_RAW_LINES = 300
MAX_LINE_ITEMS = 150

_CURRENCY = re.compile(r"^[A-Z]{3}$")


class VisionExtractionError(Exception):
    """Vision extraction unavailable/failed — fall back to deterministic OCR."""


def _select(images: list[Any], cap: int) -> list[Any]:
    """First ``cap - 2`` images plus the last two (totals sit on final pages)."""
    if len(images) <= cap:
        return images
    return images[: cap - 2] + images[-2:]


def _encode(images: list[Any]) -> list[str]:
    """PIL images → bounded JPEG base64 payloads."""
    encoded = []
    for img in _select(images, MAX_IMAGES):
        rgb = img.convert("RGB")
        rgb.thumbnail((MAX_IMAGE_DIM, MAX_IMAGE_DIM))
        buf = io.BytesIO()
        rgb.save(buf, "JPEG", quality=_JPEG_QUALITY)
        encoded.append(base64.b64encode(buf.getvalue()).decode("ascii"))
    return encoded


def _str(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _amount(value: Any) -> Optional[Decimal]:
    """Strict code-side validation of a transcribed amount (Principle I)."""
    text = _str(value) if not isinstance(value, (int, float)) else str(value)
    if text is None:
        return None
    try:
        return parse_inr(text)
    except INRParseError:
        return None


def _decimal_str(value: Decimal) -> str:
    return format(value, "f")


def _trace(raw_lines: list[str], needle: Optional[str]) -> Optional[SourceRef]:
    """Best-effort trace: the first transcribed line containing the value."""
    if not needle:
        return None
    low = needle.lower()
    digits = low.replace(",", "")
    # Short all-digit tokens (quantities like "2") match as standalone tokens
    # only, so they don't trace to the first line containing that digit.
    token = re.compile(rf"\b{re.escape(digits)}\b") if digits.isdigit() and len(digits) <= 2 else None
    for idx, line in enumerate(raw_lines):
        line_low = line.lower()
        if token is not None:
            if token.search(line_low):
                return SourceRef(page=0, line=idx, raw_text=line)
        # Amounts re-gain their printed thousands separators in raw_lines, so
        # also try the bare digit run (commas stripped) when the token misses.
        elif low in line_low or digits in line_low.replace(",", ""):
            return SourceRef(page=0, line=idx, raw_text=line)
    return None


def _traced(
    value: str, raw_lines: list[str], conf: float, needle: Optional[str] = None
) -> TracedValue:
    return TracedValue(
        value=value,
        provenance=Provenance.extracted,
        confidence=conf,
        source_ref=_trace(raw_lines, needle or value),
    )


def _traced_amount(
    value: Any, raw_lines: list[str], conf: float
) -> Optional[TracedValue]:
    amount = _amount(value)
    if amount is None:
        return None
    return _traced(
        _decimal_str(amount), raw_lines, conf, needle=_str(value) or _decimal_str(amount)
    )


def _bill_date(value: Any, raw_lines: list[str], conf: float) -> Optional[TracedValue]:
    text = _str(value)
    if text is None:
        return None
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        return None
    return _traced(parsed.isoformat(), raw_lines, conf)


def _tax(data: dict[str, Any], raw_lines: list[str], conf: float) -> tuple[
    Optional[TracedValue], Optional[TracedValue]
]:
    """(tax_amount, tax_rate): single printed figure, else components summed in code."""
    tax_amount = _traced_amount(data.get("tax_amount"), raw_lines, conf)
    rate = _amount(data.get("tax_rate"))
    tax_rate = _traced(_decimal_str(rate), raw_lines, conf) if rate is not None else None
    if tax_amount is not None:
        return tax_amount, tax_rate

    components = data.get("tax_components")
    if not isinstance(components, list):
        return None, tax_rate
    comp_total = Decimal(0)
    comp_rates: list[Decimal] = []
    count = 0
    first_ref: Optional[SourceRef] = None
    for comp in components:
        if not isinstance(comp, dict):
            continue
        amount = _amount(comp.get("amount"))
        if amount is None:
            continue
        comp_total += amount
        count += 1
        first_ref = first_ref or _trace(raw_lines, _str(comp.get("amount")))
        comp_rate = _amount(comp.get("rate"))
        if comp_rate is not None:
            comp_rates.append(comp_rate)
    if count == 0:
        return None, tax_rate
    tax_amount = TracedValue(
        value=_decimal_str(comp_total),
        provenance=Provenance.extracted,
        confidence=conf,
        source_ref=first_ref,
    )
    # When every printed component carries the same rate (the standard
    # CGST 2.5% + SGST 2.5% split), their sum is the bill's effective rate and
    # outranks any single-component rate the model echoed into the top-level
    # field. Mixed brackets (a 5% row next to an 18% row) have no single
    # effective rate — leave it unset so the tax check is skipped as
    # unverifiable rather than flagged from a fabricated rate.
    if comp_rates and all(r == comp_rates[0] for r in comp_rates):
        total_rate = sum(comp_rates, Decimal(0))
        if total_rate > 0:
            tax_rate = TracedValue(
                value=_decimal_str(total_rate),
                provenance=Provenance.extracted,
                confidence=conf,
                source_ref=first_ref,
            )
    elif comp_rates:
        tax_rate = None
    return tax_amount, tax_rate


def _line_items(data: dict[str, Any], raw_lines: list[str], conf: float) -> list[LineItem]:
    items: list[LineItem] = []
    raw_items = data.get("line_items")
    if not isinstance(raw_items, list):
        return items
    for raw in raw_items[:MAX_LINE_ITEMS]:
        if not isinstance(raw, dict):
            continue
        description = _str(raw.get("description"))
        line_total = _traced_amount(raw.get("line_total"), raw_lines, conf)
        # An item without a code-validated printed amount cannot be verified —
        # skipped rather than carried with a fabricated/None figure.
        if description is None or line_total is None:
            continue
        items.append(
            LineItem(
                position=len(items),
                description=_traced(description, raw_lines, conf),
                quantity=_traced_amount(raw.get("quantity"), raw_lines, conf),
                unit_amount=_traced_amount(raw.get("unit_amount"), raw_lines, conf),
                line_total=line_total,
            )
        )
    return items


def _swap_computed_totals(items: list[LineItem]) -> Optional[list[LineItem]]:
    """Variant replacing untraced line totals with the traced printed amount.

    Despite the transcribe-only prompt, the model sometimes multiplies
    quantity × price into a line_total that is printed nowhere (its trace
    fails) while the amount actually printed on the row sits in unit_amount
    (traced). Returns the swapped variant, or None when no item qualifies —
    the caller keeps whichever variant the code-side reconciliation score
    proves more consistent (Principle I: figures must come from the bill).
    """
    swapped = False
    out: list[LineItem] = []
    for item in items:
        unit = item.unit_amount
        if (
            item.line_total.source_ref is None
            and unit is not None
            and unit.source_ref is not None
        ):
            out.append(item.model_copy(update={"line_total": unit}))
            swapped = True
        else:
            out.append(item)
    return out if swapped else None


def _bill_type(data: dict[str, Any], raw_text: str, hint: Optional[str]) -> BillType:
    if hint in (BillType.telecom_recharge.value, BillType.grocery.value):
        return BillType(hint)
    claimed = data.get("bill_type")
    if claimed in (BillType.telecom_recharge.value, BillType.grocery.value):
        return BillType(claimed)
    return detect_bill_type(raw_text)


def extract_bill(
    images: list[Any], bill_type_hint: Optional[str] = None, partial: bool = False
) -> Bill:
    """Transcribe bill image(s) via the vision LLM and assemble a candidate.

    ``partial=True`` means the caller already dropped pages (cap); when this
    call drops images beyond ``MAX_IMAGES`` the result is partial too.
    """
    partial = partial or len(images) > MAX_IMAGES
    payload = _encode(images)
    try:
        from src.services.llm_service import get_llm_service

        data = get_llm_service().extract_bill_image(payload)
    except Exception as exc:  # noqa: BLE001 - any provider failure → fallback
        raise VisionExtractionError(str(exc)) from exc
    if not isinstance(data, dict) or not data:
        raise VisionExtractionError("empty vision response")

    if data.get("is_bill") is False:
        raise NotABillError()

    conf = DEGRADED_CONFIDENCE if data.get("legibility") == "degraded" else VISION_CONFIDENCE

    raw_lines = [
        ln.strip()
        for ln in data.get("raw_lines", [])
        if isinstance(ln, str) and ln.strip()
    ][:MAX_RAW_LINES]
    raw_text = "\n".join(raw_lines)

    merchant_name = _str(data.get("merchant"))
    merchant = (
        _traced(merchant_name, raw_lines, conf)
        if merchant_name
        else TracedValue(value=None, provenance=Provenance.extracted)
    )

    total = _traced_amount(data.get("total_amount"), raw_lines, conf)
    subtotal = _traced_amount(data.get("subtotal"), raw_lines, conf)
    tax_amount, tax_rate = _tax(data, raw_lines, conf)
    line_items = _line_items(data, raw_lines, conf)

    if total is None and not line_items:
        # The model saw a bill but transcribed nothing verifiable — let the
        # deterministic pipeline have a go rather than declining outright.
        raise VisionExtractionError("vision transcription carried no usable figures")

    currency = _str(data.get("currency")) or ""
    currency = currency.upper() if _CURRENCY.match(currency.upper()) else "INR"

    # The printed taxable value (GST-summary base) outranks the
    # subtotal-as-base assumption — on tax-inclusive receipts the subtotal
    # already contains the tax and would yield a false tax-mismatch flag.
    tax_base = _traced_amount(data.get("taxable_value"), raw_lines, conf)
    if tax_base is None and tax_rate is not None:
        tax_base = subtotal

    bill = Bill(
        merchant=merchant,
        bill_type=_bill_type(data, raw_text, bill_type_hint),
        bill_date=_bill_date(data.get("bill_date"), raw_lines, conf),
        currency=currency,
        subtotal=subtotal,
        tax_rate=tax_rate,
        tax_base=tax_base,
        tax_amount=tax_amount,
        total_amount=total or TracedValue(value=None, provenance=Provenance.extracted),
        line_items=line_items,
        # A known-partial extraction can't itemize the whole bill, so its sums
        # can't PROVE anything (Principle II) — suppress arithmetic checks.
        nothing_to_verify=(total is not None and not line_items) or partial,
        # The vision model reads any printed layout, so an off-list bill type
        # (electricity, water, ...) is extracted data, not an unsupported layout.
        layout_supported=True,
        status="candidate",
    )
    if partial:
        logger.warning(
            "vision extraction is partial (pages dropped) — arithmetic checks suppressed"
        )

    # Guard against model-computed line totals: when an untraced total exists
    # alongside a traced printed amount, keep whichever variant the
    # reconciliation score proves more internally consistent.
    alt_items = _swap_computed_totals(line_items)
    if alt_items is not None:
        from src.services.structure_service import _score as _consistency_score

        alt_bill = bill.model_copy(update={"line_items": alt_items})
        if _consistency_score(alt_bill) > _consistency_score(bill):
            logger.info("vision: replaced computed line totals with printed amounts")
            bill = alt_bill

    return bill

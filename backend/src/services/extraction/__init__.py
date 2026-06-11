"""Extraction orchestrator: raw input(s) → one structured Bill candidate.

Routes by input kind, runs the deterministic extractor, picks a per-type parser,
and applies the minimal non-bill guard (T021): if nothing bill-like can be
located (no total and no line items) or overall confidence is below the floor,
raise ``NotABillError`` so the API declines gracefully (cheap FR-021) instead of
emitting fabricated fields.
"""

from __future__ import annotations

from typing import Optional

from src.models import Bill, BillType
from src.services.extraction.ocr import extract_image
from src.services.extraction.pdf import extract_pdf
from src.services.extraction.text import extract_text
from src.services.extraction.types import ExtractionResult
from src.services.parsers import grocery, telecom

# Below this overall confidence we treat the input as unreadable for the demo.
CONFIDENCE_FLOOR = 0.35


class NotABillError(Exception):
    """Raised when input cannot be read as a bill (declined, not fabricated)."""

    def __init__(self, reason: str = "Input is not a recognizable bill.") -> None:
        super().__init__(reason)
        self.reason = reason


def _detect_bill_type(result: ExtractionResult) -> BillType:
    low = result.raw_text.lower()

    # Strong signals are decisive (telecom checked first: a recharge bill is
    # unambiguously telecom even if it carries generic invoice vocabulary).
    if any(kw in low for kw in telecom.STRONG):
        return BillType.telecom_recharge
    if any(kw in low for kw in grocery.STRONG):
        return BillType.grocery

    # Otherwise fall back to weighted keyword counts.
    telecom_hits = sum(1 for kw in telecom.KEYWORDS if kw in low)
    grocery_hits = sum(1 for kw in grocery.KEYWORDS if kw in low)
    if telecom_hits == 0 and grocery_hits == 0:
        return BillType.unsupported
    return BillType.telecom_recharge if telecom_hits >= grocery_hits else BillType.grocery


def _extract(
    files: Optional[list[tuple[bytes, str, str]]],
    text: Optional[str],
) -> ExtractionResult:
    if text and text.strip():
        return extract_text(text)
    if not files:
        raise NotABillError("No bill input provided.")

    combined: Optional[ExtractionResult] = None
    for file_bytes, filename, content_type in files:
        is_pdf = content_type == "application/pdf" or filename.lower().endswith(".pdf")
        part = extract_pdf(file_bytes) if is_pdf else extract_image(file_bytes)
        combined = part if combined is None else combined.merge(part)
    assert combined is not None
    return combined


def process_inputs(
    files: Optional[list[tuple[bytes, str, str]]] = None,
    text: Optional[str] = None,
    bill_type_hint: Optional[str] = None,
) -> Bill:
    result = _extract(files, text)

    # Non-bill guard (T021).
    if result.confidence < CONFIDENCE_FLOOR:
        raise NotABillError("Couldn't read a bill — the image is too unclear.")

    if bill_type_hint in (BillType.telecom_recharge.value, BillType.grocery.value):
        bill_type = BillType(bill_type_hint)
    else:
        bill_type = _detect_bill_type(result)

    parser = telecom if bill_type == BillType.telecom_recharge else grocery
    candidate = parser.parse(result)

    # If we located neither a total nor any line items, it isn't a bill.
    if candidate.total_amount.value is None and not candidate.line_items:
        raise NotABillError()

    # LLM structure labeling: refine WHICH lines mean what (never the figures);
    # accepted only when code-side reconciliation proves it more consistent.
    from src.services.structure_service import refine

    return refine(result, candidate)

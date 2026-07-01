"""Extraction orchestrator: raw input(s) → one structured Bill candidate.

v2 routing (Constitution v2.0.0): image uploads and fully scanned PDFs go to
the vision-LLM transcriber first (extraction/vision.py) — markedly more
accurate than local OCR on phone photos. Any vision failure falls back to the
v1 deterministic pipeline (OCR → keyword parser → LLM structure labels), so a
missing key or provider outage degrades accuracy rather than disabling image
bills. PDF text layers and pasted text stay purely deterministic — a lossless
text layer is never sent for vision re-reading.

Both paths end behind the same guard: if nothing bill-like can be located, the
API declines with ``NotABillError`` (FR-021) instead of emitting fabricated
fields.
"""

from __future__ import annotations

import io
import logging
from typing import Optional

from src.config import get_settings
from src.models import Bill, BillType
from src.services.extraction.ocr import extract_image
from src.services.extraction.pdf import PdfTooLargeError, extract_pdf, rasterize_scanned
from src.services.extraction.text import extract_text
from src.services.extraction.types import ExtractionResult, NotABillError
from src.services.parsers import detect_bill_type, grocery, telecom

logger = logging.getLogger("billology.extraction")

# Below this overall confidence we treat the input as unreadable for the demo.
CONFIDENCE_FLOOR = 0.35

__all__ = ["NotABillError", "process_inputs"]


def _is_pdf(filename: str, content_type: str) -> bool:
    return content_type == "application/pdf" or filename.lower().endswith(".pdf")


def _vision_images(files: list[tuple[bytes, str, str]]) -> tuple[Optional[list], bool]:
    """(PIL images, partial?) for the vision path; images is None when
    deterministic parsing wins.

    Any PDF with a native text layer routes the whole submission to the
    deterministic path (the text layer is lossless). ``partial`` is True when
    scanned pages were dropped to fit the vision cap. May raise
    ``PdfTooLargeError`` — an oversized PDF is declined, not processed.
    """
    from PIL import Image  # lazy

    images: list = []
    partial = False
    for file_bytes, filename, content_type in files:
        if _is_pdf(filename, content_type):
            rasterized = rasterize_scanned(file_bytes)
            if rasterized is None:
                return None, False
            pages, page_partial = rasterized
            images.extend(pages)
            partial = partial or page_partial
        else:
            images.append(Image.open(io.BytesIO(file_bytes)))
    return (images or None), partial


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
        try:
            part = (
                extract_pdf(file_bytes)
                if _is_pdf(filename, content_type)
                else extract_image(file_bytes)
            )
        except PdfTooLargeError as exc:
            raise NotABillError(str(exc)) from exc
        combined = part if combined is None else combined.merge(part)
    assert combined is not None
    return combined


def _process_classic(
    files: Optional[list[tuple[bytes, str, str]]],
    text: Optional[str],
    bill_type_hint: Optional[str],
) -> Bill:
    """v1 deterministic pipeline: extract → keyword parser → structure labels."""
    result = _extract(files, text)

    # Non-bill guard (T021).
    if result.confidence < CONFIDENCE_FLOOR:
        raise NotABillError("Couldn't read a bill — the image is too unclear.")

    if bill_type_hint in (BillType.telecom_recharge.value, BillType.grocery.value):
        bill_type = BillType(bill_type_hint)
    else:
        bill_type = detect_bill_type(result.raw_text)

    parser = telecom if bill_type == BillType.telecom_recharge else grocery
    candidate = parser.parse(result)

    # If we located neither a total nor any line items, it isn't a bill.
    if candidate.total_amount.value is None and not candidate.line_items:
        raise NotABillError()

    # LLM structure labeling: refine WHICH lines mean what (never the figures);
    # accepted only when code-side reconciliation proves it more consistent.
    from src.services.structure_service import refine

    return refine(result, candidate)


def _finalize(bill: Bill) -> Bill:
    """Code-side post-processing shared by every extraction path.

    Recovers a tax the recognizer missed from the printed subtotal/total so it
    is shown for review and a reconciling bill isn't falsely flagged. Pure
    arithmetic over already-extracted figures (Principle I).
    """
    from src.services.arithmetic_service import derive_tax_if_missing

    derive_tax_if_missing(bill)
    return bill


def process_inputs(
    files: Optional[list[tuple[bytes, str, str]]] = None,
    text: Optional[str] = None,
    bill_type_hint: Optional[str] = None,
) -> Bill:
    if (not text or not text.strip()) and files and get_settings().vision_extraction:
        try:
            images, partial = _vision_images(files)
        except PdfTooLargeError as exc:
            raise NotABillError(str(exc)) from exc
        except Exception:  # noqa: BLE001 - unreadable file: let v1 raise its usual error
            images, partial = None, False
        if images:
            from src.services.extraction import vision

            try:
                return _finalize(vision.extract_bill(images, bill_type_hint, partial=partial))
            except vision.VisionExtractionError as exc:
                logger.warning("vision extraction unavailable, falling back to local OCR: %s", exc)

    return _finalize(_process_classic(files, text, bill_type_hint))

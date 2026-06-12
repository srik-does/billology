"""PDF extraction.

Prefers the native text layer (pdfplumber) — lossless, no OCR error. Pages with
no extractable text are rasterized (pdf2image) and routed through the image OCR
path so scanned-PDF bills still work. All pages are assembled into one logical
bill (FR-002).
"""

from __future__ import annotations

import io
import logging

from src.models import ArtifactKind

from .types import ExtractionLine, ExtractionResult

logger = logging.getLogger(__name__)

# Bills longer than this are declined with a friendly message instead of
# tying up the instance for minutes (each scanned page costs an OCR pass).
MAX_PAGES = 12

# Cap how many *scanned* (no-text-layer) pages get an OCR pass. Per-page OCR is
# slow on a small shared CPU (free-tier hosting), and the request sits behind a
# ~100 s edge/gateway timeout — past which a long scanned PDF returns NOTHING.
# Bills carry their merchant and grand total on the first or last page, so when
# a scanned PDF exceeds the cap we OCR the first pages plus the last one rather
# than time out. Text-layer pages are cheap (pdfplumber) and are never capped.
MAX_OCR_PAGES = 4

# OCR doesn't benefit from more: the detector downscales internally, and
# 200 DPI (the pdf2image default) doubles the per-page bitmap for nothing.
_RASTER_DPI = 150


class PdfTooLargeError(Exception):
    def __init__(self, pages: int) -> None:
        super().__init__(
            f"This PDF has {pages} pages — bills over {MAX_PAGES} pages aren't supported yet."
        )


def extract_pdf(file_bytes: bytes) -> ExtractionResult:
    import pdfplumber  # lazy: heavy dependency

    result = ExtractionResult(kind=ArtifactKind.pdf, confidence=1.0)
    raw_chunks: list[str] = []
    image_pages: list[int] = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        if len(pdf.pages) > MAX_PAGES:
            raise PdfTooLargeError(len(pdf.pages))
        for page_no, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ""
            if page_text.strip():
                raw_chunks.append(page_text)
                for line_no, raw in enumerate(page_text.splitlines()):
                    stripped = raw.strip()
                    if stripped:
                        result.lines.append(
                            ExtractionLine(
                                text=stripped, page=page_no, line=line_no, confidence=1.0
                            )
                        )
            else:
                image_pages.append(page_no)

    if image_pages:
        # No text layer on these pages → rasterize + OCR (bounded — see below).
        pages_to_ocr = _select_ocr_pages(image_pages, MAX_OCR_PAGES)
        if len(pages_to_ocr) < len(image_pages):
            logger.warning(
                "Scanned PDF has %d image pages; OCR limited to %d (pages %s) to "
                "stay within the request timeout — result may be partial.",
                len(image_pages), len(pages_to_ocr), [p + 1 for p in pages_to_ocr],
            )
        _ocr_image_pages(file_bytes, pages_to_ocr, result)

    result.raw_text = "\n".join(raw_chunks).strip()
    return result


def rasterize_scanned(file_bytes: bytes) -> "list | None":
    """Page images for the vision path when the PDF is fully scanned, else None.

    A PDF with any native text layer stays on the deterministic path — the text
    layer is lossless, so vision re-reading it could only add transcription
    risk. Page selection reuses the OCR cap rationale: first pages plus the
    last, where merchant and grand total live.
    """
    import pdfplumber  # lazy

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        if len(pdf.pages) > MAX_PAGES:
            raise PdfTooLargeError(len(pdf.pages))
        if any((page.extract_text() or "").strip() for page in pdf.pages):
            return None
        page_nos = _select_ocr_pages(list(range(len(pdf.pages))), MAX_OCR_PAGES)

    from pdf2image import convert_from_bytes  # lazy

    images = []
    for page_no in page_nos:  # one page at a time — same OOM guard as OCR below
        page_images = convert_from_bytes(
            file_bytes, dpi=_RASTER_DPI, first_page=page_no + 1, last_page=page_no + 1
        )
        if page_images:
            images.append(page_images[0])
    return images


def _select_ocr_pages(image_pages: list[int], cap: int) -> list[int]:
    """Choose which scanned pages to OCR when there are more than the cap.

    Keeps the first ``cap - 1`` pages plus the last page (a grand total often
    sits on the final page), preserving page order and de-duplicating when the
    last page is already among the first ones.
    """
    if len(image_pages) <= cap:
        return image_pages
    chosen = image_pages[: cap - 1] + image_pages[-1:]
    # De-dupe while preserving order (last page could coincide with the head).
    seen: set[int] = set()
    return [p for p in chosen if not (p in seen or seen.add(p))]


def _ocr_image_pages(file_bytes: bytes, pages: list[int], result: ExtractionResult) -> None:
    from pdf2image import convert_from_bytes  # lazy

    from .ocr import extract_image_object

    # One page at a time: rasterizing the whole document at once held every
    # page bitmap in memory simultaneously (~12 MB each), which OOM-killed
    # 512 MB deployment instances on multi-page scanned PDFs.
    for page_no in pages:
        images = convert_from_bytes(
            file_bytes, dpi=_RASTER_DPI, first_page=page_no + 1, last_page=page_no + 1
        )
        if not images:
            continue
        page_result = extract_image_object(images[0])
        for ln in page_result.lines:
            result.lines.append(
                ExtractionLine(
                    text=ln.text, page=page_no, line=ln.line,
                    bbox=ln.bbox, confidence=ln.confidence,
                )
            )
        result.raw_text = f"{result.raw_text}\n{page_result.raw_text}".strip()
        result.confidence = min(result.confidence, page_result.confidence)

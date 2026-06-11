"""PDF extraction.

Prefers the native text layer (pdfplumber) — lossless, no OCR error. Pages with
no extractable text are rasterized (pdf2image) and routed through the image OCR
path so scanned-PDF bills still work. All pages are assembled into one logical
bill (FR-002).
"""

from __future__ import annotations

import io

from src.models import ArtifactKind

from .types import ExtractionLine, ExtractionResult


def extract_pdf(file_bytes: bytes) -> ExtractionResult:
    import pdfplumber  # lazy: heavy dependency

    result = ExtractionResult(kind=ArtifactKind.pdf, confidence=1.0)
    raw_chunks: list[str] = []
    image_pages: list[int] = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
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
        # No text layer on these pages → rasterize + OCR.
        _ocr_image_pages(file_bytes, image_pages, result)

    result.raw_text = "\n".join(raw_chunks).strip()
    return result


def _ocr_image_pages(file_bytes: bytes, pages: list[int], result: ExtractionResult) -> None:
    from pdf2image import convert_from_bytes  # lazy

    from .ocr import extract_image_object

    images = convert_from_bytes(file_bytes)
    for page_no in pages:
        if page_no >= len(images):
            continue
        page_result = extract_image_object(images[page_no])
        for ln in page_result.lines:
            result.lines.append(
                ExtractionLine(
                    text=ln.text, page=page_no, line=ln.line,
                    bbox=ln.bbox, confidence=ln.confidence,
                )
            )
        result.raw_text = f"{result.raw_text}\n{page_result.raw_text}".strip()
        result.confidence = min(result.confidence, page_result.confidence)

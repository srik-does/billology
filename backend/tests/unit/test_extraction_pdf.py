"""PDF extraction guards: oversized scanned PDFs are declined, not processed."""

from __future__ import annotations

import io

import pytest

from src.services.extraction import NotABillError, process_inputs
from src.services.extraction.pdf import MAX_PAGES, PdfTooLargeError, extract_pdf


def _pdf_bytes(pages: int) -> bytes:
    from PIL import Image

    images = [Image.new("RGB", (200, 280), "white") for _ in range(pages)]
    buf = io.BytesIO()
    images[0].save(buf, "PDF", save_all=True, append_images=images[1:])
    return buf.getvalue()


def test_pdf_over_page_cap_raises_before_any_ocr():
    with pytest.raises(PdfTooLargeError) as exc:
        extract_pdf(_pdf_bytes(MAX_PAGES + 1))
    assert str(MAX_PAGES) in str(exc.value)


def test_oversized_pdf_is_declined_with_friendly_reason():
    files = [(_pdf_bytes(MAX_PAGES + 1), "long-bill.pdf", "application/pdf")]
    with pytest.raises(NotABillError) as exc:
        process_inputs(files=files)
    assert "pages" in exc.value.reason

"""Single clean-image OCR via Tesseract (inside the trust boundary, Principle IV).

Light Pillow preprocessing (grayscale) then word-level OCR so each token carries
a confidence and bounding box for traceability (NFR-Reliability). Words are
grouped back into lines by Tesseract's block/line numbering.

Image-quality gating and multi-image assembly are out of the demo spine
(deferred T042/T043; cut T044/T045) — this path assumes one reasonably clean image.
"""

from __future__ import annotations

import io
from collections import defaultdict
from typing import Any

from src.models import ArtifactKind

from .types import ExtractionLine, ExtractionResult


def extract_image(file_bytes: bytes) -> ExtractionResult:
    from PIL import Image  # lazy

    image = Image.open(io.BytesIO(file_bytes))
    return extract_image_object(image)


def extract_image_object(image: Any) -> ExtractionResult:
    """OCR a PIL image. Separated so the PDF path can reuse it per rasterized page."""
    import pytesseract  # lazy
    from pytesseract import Output

    gray = image.convert("L")
    data = pytesseract.image_to_data(gray, output_type=Output.DICT)

    # Group words into lines keyed by (block, par, line).
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    confidences: list[float] = []
    n = len(data["text"])
    for i in range(n):
        word = (data["text"][i] or "").strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if not word or conf < 0:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        groups[key].append(
            {
                "word": word,
                "conf": conf,
                "left": data["left"][i],
                "top": data["top"][i],
                "width": data["width"][i],
                "height": data["height"][i],
            }
        )
        confidences.append(conf / 100.0)

    result = ExtractionResult(kind=ArtifactKind.image)
    raw_lines: list[str] = []
    for line_no, (_key, words) in enumerate(sorted(groups.items())):
        text = " ".join(w["word"] for w in words)
        left = min(w["left"] for w in words)
        top = min(w["top"] for w in words)
        right = max(w["left"] + w["width"] for w in words)
        bottom = max(w["top"] + w["height"] for w in words)
        line_conf = sum(w["conf"] for w in words) / len(words) / 100.0
        result.lines.append(
            ExtractionLine(
                text=text, page=0, line=line_no,
                bbox=[float(left), float(top), float(right), float(bottom)],
                confidence=line_conf,
            )
        )
        raw_lines.append(text)

    result.raw_text = "\n".join(raw_lines)
    result.confidence = (sum(confidences) / len(confidences)) if confidences else 0.0
    return result

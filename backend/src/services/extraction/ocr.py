"""Single clean-image OCR (inside the trust boundary, Principle IV).

Default engine is RapidOCR — PP-OCRv4 detection + English recognition running
locally on ONNX Runtime (CPU). It replaces Tesseract as the primary because it
is markedly more accurate on phone photos of receipts (benchmarked in
``scripts/compare_ocr.py``: at the severe degradation tier it recovers more
amount tokens at 0.89 mean confidence vs Tesseract's 0.52, and emits no junk
lines). Tesseract remains as a fallback so a missing model file or a broken
onnxruntime install degrades accuracy rather than disabling image bills.

Both engines produce the same line model: text + bounding box + confidence per
line (NFR-Reliability traceability). RapidOCR detects line-level boxes which
are clustered by vertical center into visual lines; Tesseract's word boxes are
grouped by its block/line numbering.

Image-quality gating and multi-image assembly are out of the demo spine
(deferred T042/T043; cut T044/T045) — this path assumes one reasonably clean image.
"""

from __future__ import annotations

import io
import logging
import os
import threading
from collections import defaultdict
from typing import Any

from src.models import ArtifactKind

from .types import ExtractionLine, ExtractionResult

logger = logging.getLogger(__name__)

# Measured on a 38-box receipt (i7-12650H): RapidOCR's default ORT threading
# runs ~22s vs ~1.5s with explicit intra-op threads. More threads is not
# better — on hybrid P/E-core CPUs the spinning thread pool degrades sharply
# when threads straddle core types (8 threads: 11s vs 4 threads: 6.5s under
# sustained load), so cap low rather than scaling with cpu_count.
_INTRA_OP_THREADS = min(4, os.cpu_count() or 4)

_rapidocr_engine: Any = None
_rapidocr_lock = threading.Lock()


def _get_rapidocr() -> Any:
    """Process-wide engine singleton.

    Must be created before any pytesseract subprocess call: ONNX sessions
    created after one run ~10x slower for the life of the process (measured on
    Windows). With RapidOCR as the default engine that ordering holds naturally.
    """
    global _rapidocr_engine
    if _rapidocr_engine is None:
        with _rapidocr_lock:
            if _rapidocr_engine is None:
                from rapidocr import LangRec, RapidOCR

                _rapidocr_engine = RapidOCR(
                    params={
                        "Rec.lang_type": LangRec.EN,
                        # The angle classifier costs ~16s/receipt regardless of
                        # threading and only fixes upside-down text.
                        "Global.use_cls": False,
                        "EngineConfig.onnxruntime.intra_op_num_threads": _INTRA_OP_THREADS,
                    }
                )
    return _rapidocr_engine


def extract_image(file_bytes: bytes) -> ExtractionResult:
    from PIL import Image  # lazy

    image = Image.open(io.BytesIO(file_bytes))
    return extract_image_object(image)


def extract_image_object(image: Any) -> ExtractionResult:
    """OCR a PIL image. Separated so the PDF path can reuse it per rasterized page."""
    try:
        return _extract_rapidocr(image)
    except Exception:
        logger.warning("RapidOCR unavailable or failed; falling back to Tesseract", exc_info=True)
        return _extract_tesseract(image)


def _extract_rapidocr(image: Any) -> ExtractionResult:
    import numpy as np

    # No upscaling/contrast preprocessing: the PP-OCR detector rescales
    # internally, and feeding it the raw image benchmarked both faster and as
    # accurate as the Tesseract-tuned preprocessing.
    output = _get_rapidocr()(np.asarray(image.convert("RGB")))

    result = ExtractionResult(kind=ArtifactKind.image)
    texts = list(output.txts or [])
    if not texts:
        result.confidence = 0.0
        return result
    scores = list(output.scores or [])

    dets = []
    for i, text in enumerate(texts):
        xs = [float(p[0]) for p in output.boxes[i]]
        ys = [float(p[1]) for p in output.boxes[i]]
        dets.append(
            {
                "text": text,
                "score": float(scores[i]) if i < len(scores) else 0.0,
                "left": min(xs),
                "top": min(ys),
                "right": max(xs),
                "bottom": max(ys),
                "cy": (min(ys) + max(ys)) / 2,
                "h": max(ys) - min(ys),
            }
        )

    # Cluster detections into visual lines: top-to-bottom, then boxes whose
    # vertical centers sit within half a line height join the same line.
    dets.sort(key=lambda d: d["cy"])
    groups: list[list[dict[str, Any]]] = []
    for det in dets:
        if (
            groups
            and abs(det["cy"] - groups[-1][0]["cy"]) < max(det["h"], groups[-1][0]["h"]) * 0.5
        ):
            groups[-1].append(det)
        else:
            groups.append([det])

    raw_lines: list[str] = []
    for line_no, group in enumerate(groups):
        group.sort(key=lambda d: d["left"])
        text = " ".join(d["text"] for d in group)
        result.lines.append(
            ExtractionLine(
                text=text,
                page=0,
                line=line_no,
                bbox=[
                    min(d["left"] for d in group),
                    min(d["top"] for d in group),
                    max(d["right"] for d in group),
                    max(d["bottom"] for d in group),
                ],
                confidence=sum(d["score"] for d in group) / len(group),
            )
        )
        raw_lines.append(text)

    result.raw_text = "\n".join(raw_lines)
    result.confidence = sum(d["score"] for d in dets) / len(dets)
    return result


def _extract_tesseract(image: Any) -> ExtractionResult:
    import pytesseract  # lazy
    from PIL import Image, ImageOps
    from pytesseract import Output

    gray = image.convert("L")
    # Phone photos of receipts are often small/low-contrast; upscaling to a
    # minimum width plus autocontrast measurably lifts Tesseract accuracy
    # (verified on a 342px-wide thermal receipt: avg conf 0.39 → 0.51, with the
    # total and merchant recovered). --psm 4 fits the single-column layout.
    if gray.width < 1000:
        scale = max(2, round(1000 / gray.width))
        gray = gray.resize((gray.width * scale, gray.height * scale), Image.Resampling.LANCZOS)
    gray = ImageOps.autocontrast(gray, cutoff=2)
    data = pytesseract.image_to_data(gray, output_type=Output.DICT, config="--psm 4")

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
                text=text,
                page=0,
                line=line_no,
                bbox=[float(left), float(top), float(right), float(bottom)],
                confidence=line_conf,
            )
        )
        raw_lines.append(text)

    result.raw_text = "\n".join(raw_lines)
    result.confidence = (sum(confidences) / len(confidences)) if confidences else 0.0
    return result

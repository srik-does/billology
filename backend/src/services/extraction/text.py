"""Pasted-text extraction — normalize raw text into line tokens.

No OCR involved; confidence is 1.0 (the user gave us the characters directly).
"""

from __future__ import annotations

from src.models import ArtifactKind

from .types import ExtractionLine, ExtractionResult


def extract_text(text: str) -> ExtractionResult:
    result = ExtractionResult(kind=ArtifactKind.text, raw_text=text or "", confidence=1.0)
    for idx, raw in enumerate(result.raw_text.splitlines()):
        stripped = raw.strip()
        if stripped:
            result.lines.append(ExtractionLine(text=stripped, page=0, line=idx, confidence=1.0))
    return result

"""Shared intermediate produced by every extractor before parsing.

OCR, PDF text-layer, and pasted-text all converge to an ``ExtractionResult`` so a
single set of per-type parsers can serve all three input formats (FR-001). The
extractors are the *sole producers* of text/figures (Principle I); parsers and
the LLM only interpret what lands here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.models import ArtifactKind


class NotABillError(Exception):
    """Raised when input cannot be read as a bill (declined, not fabricated)."""

    def __init__(self, reason: str = "Input is not a recognizable bill.") -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class ExtractionLine:
    """One line of recognized text with its trace and confidence."""

    text: str
    page: int = 0
    line: int = 0
    bbox: Optional[list[float]] = None
    confidence: Optional[float] = None  # 0..1; None ⇒ treated as high (text layer)


@dataclass
class ExtractionResult:
    kind: ArtifactKind
    raw_text: str = ""
    lines: list[ExtractionLine] = field(default_factory=list)
    # Overall confidence in [0,1]; 1.0 for native text layers / pasted text.
    confidence: float = 1.0

    def merge(self, other: "ExtractionResult") -> "ExtractionResult":
        """Combine another result as additional pages of the same logical bill."""
        next_page = (max((ln.page for ln in self.lines), default=-1) + 1) if self.lines else 0
        for ln in other.lines:
            self.lines.append(
                ExtractionLine(
                    text=ln.text,
                    page=next_page + ln.page,
                    line=ln.line,
                    bbox=ln.bbox,
                    confidence=ln.confidence,
                )
            )
        self.raw_text = f"{self.raw_text}\n{other.raw_text}".strip()
        self.confidence = min(self.confidence, other.confidence)
        return self

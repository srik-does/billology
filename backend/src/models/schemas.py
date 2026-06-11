"""Canonical Pydantic schemas — the single structured representation (Principle III).

Every value-bearing field is wrapped in a ``TracedValue`` carrying provenance
(extracted-from-source vs. user-provided), an optional confidence, and a source
trace. Money is represented as a string in transit and parsed to ``Decimal`` for
arithmetic — never float (see services/parsers/inr.py and arithmetic_service).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class Provenance(str, Enum):
    extracted = "extracted"
    user_provided = "user_provided"


class BillType(str, Enum):
    telecom_recharge = "telecom_recharge"
    grocery = "grocery"
    unsupported = "unsupported"


class ArtifactKind(str, Enum):
    image = "image"
    pdf = "pdf"
    text = "text"


class DiscrepancyKind(str, Enum):
    sum_mismatch = "sum_mismatch"
    duplicate_item = "duplicate_item"
    tax_mismatch = "tax_mismatch"


class SourceRef(BaseModel):
    """Where an extracted value came from. Null for user-provided values."""

    artifact_id: Optional[UUID] = None
    page: Optional[int] = None
    bbox: Optional[list[float]] = None
    line: Optional[int] = None
    raw_text: Optional[str] = None


class TracedValue(BaseModel):
    """A single value plus its provenance and source trace.

    ``value`` is kept as a string for monetary/date fields so that no precision
    is lost before Decimal parsing. ``source_ref``/``confidence`` are required
    only for extracted values.
    """

    value: Optional[str] = None
    provenance: Provenance = Provenance.extracted
    confidence: Optional[float] = None
    source_ref: Optional[SourceRef] = None


class LineItem(BaseModel):
    id: Optional[UUID] = None
    position: int
    description: TracedValue
    quantity: Optional[TracedValue] = None
    unit_amount: Optional[TracedValue] = None
    line_total: TracedValue


class DiscrepancyFlag(BaseModel):
    kind: DiscrepancyKind
    conflicting_figures: dict[str, Any]
    explanation_text: str = ""


class Explanation(BaseModel):
    bill_summary: str = ""
    line_explanations: dict[str, str] = Field(default_factory=dict)


class Category(BaseModel):
    id: Optional[UUID] = None
    name: str
    is_seeded: bool = False


class SourceArtifact(BaseModel):
    id: Optional[UUID] = None
    kind: ArtifactKind
    storage_path: Optional[str] = None
    page_order: int = 0
    raw_text: Optional[str] = None
    quality_score: Optional[float] = None


class Bill(BaseModel):
    id: Optional[UUID] = None
    merchant: TracedValue
    bill_type: BillType = BillType.unsupported
    bill_date: Optional[TracedValue] = None
    currency: str = "INR"
    subtotal: Optional[TracedValue] = None
    tax_rate: Optional[TracedValue] = None
    tax_base: Optional[TracedValue] = None
    tax_amount: Optional[TracedValue] = None
    total_amount: TracedValue
    category: Optional[Category] = None
    line_items: list[LineItem] = Field(default_factory=list)
    discrepancies: list[DiscrepancyFlag] = Field(default_factory=list)
    explanation: Optional[Explanation] = None
    source_artifacts: list[SourceArtifact] = Field(default_factory=list)
    layout_supported: bool = True
    nothing_to_verify: bool = False
    status: str = "candidate"  # candidate | saved

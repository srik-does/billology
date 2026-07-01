"""Shared canonical-write path: persist a Bill once, consistently.

Both the live save endpoint (T031) and the demo seed script (T034) go through
``save_bill`` so seeded and live-saved bills are byte-for-byte consistent under
semantic Q&A and dashboard aggregates (the C3 fix). The embedding text rendering
lives here and nowhere else.

Pure helpers (``embedding_text``, ``bill_row``, ``line_item_rows`` …) take no IO
and are unit-tested; ``save_bill`` performs the Supabase writes and is injected
with ``db`` / ``embed_fn`` so it can be exercised without a live database.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Optional

from src.models import Bill, TracedValue
from src.services import persistence
from src.services.embedding_service import embed as _default_embed

# --- pure helpers -----------------------------------------------------------


def _val(traced: Optional[TracedValue]) -> Optional[str]:
    return traced.value if (traced and traced.value is not None) else None


def _num(traced: Optional[TracedValue]) -> Optional[str]:
    v = _val(traced)
    if v is None:
        return None
    try:
        return str(Decimal(str(v)))
    except (InvalidOperation, ValueError):
        return None


def _ref(traced: Optional[TracedValue]) -> Optional[dict]:
    if traced and traced.source_ref is not None:
        return traced.source_ref.model_dump(mode="json", exclude_none=True)
    return None


def _prov(traced: Optional[TracedValue]) -> Optional[str]:
    return traced.provenance.value if traced and traced.provenance else None


def vector_literal(embedding: list[float]) -> str:
    """Format an embedding as a pgvector text literal: '[0.1,-0.2,...]'.

    Uses repr() so each float round-trips exactly; pgvector's input parser
    accepts standard float notation including exponents.
    """
    if not embedding:
        raise ValueError("Refusing to store an empty embedding.")
    return "[" + ",".join(repr(float(x)) for x in embedding) + "]"


def embedding_text(bill: Bill, tags: tuple[str, ...] | list[str] = ()) -> str:
    """Canonical text rendering used to embed a bill (single source of truth).

    Descriptive only (merchant, type, category, item descriptions, enrichment
    tags) so retrieval is about *what* the bill is, not its figures.
    """
    parts: list[str] = []
    if bill.merchant and bill.merchant.value:
        parts.append(bill.merchant.value)
    parts.append(bill.bill_type.value)
    if bill.category and bill.category.name:
        parts.append(bill.category.name)
    for item in bill.line_items:
        if item.description and item.description.value:
            parts.append(item.description.value)
    parts.extend(tags)
    return " | ".join(parts)


def sanitize_tags(raw: Any) -> list[str]:
    """Validate LLM enrichment output into a safe, bounded tag list.

    Tags are descriptive search labels (Principle I): strings only, lowercased,
    bounded in length and count, with pure-number tokens dropped so no figure
    can sneak into the record via enrichment.
    """
    if not isinstance(raw, (list, tuple)):
        return []
    seen: set[str] = set()
    tags: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        tag = " ".join(item.lower().split())
        if not tag or len(tag) > 40:
            continue
        if not any(ch.isalpha() for ch in tag):  # drop pure numbers/punctuation
            continue
        if tag in seen:
            continue
        seen.add(tag)
        tags.append(tag)
        if len(tags) >= 24:
            break
    return tags


def enrichment_tags(bill: Bill, llm) -> list[str]:
    """LLM search labels for a bill (tags + merchant aliases), or [] on any failure.

    The payload is amount-free (merchant, type, category, item descriptions) —
    the same privacy class as the explanation call. Enrichment is best-effort:
    a missing/failing LLM must never block a save.
    """
    if llm is None:
        return []
    payload = {
        "merchant": _val(bill.merchant),
        "bill_type": bill.bill_type.value,
        "category": bill.category.name if bill.category else None,
        "items": [
            item.description.value
            for item in bill.line_items
            if item.description and item.description.value
        ],
    }
    try:
        raw = llm.enrich_bill(payload)
    except Exception:  # noqa: BLE001 - enrichment is optional
        return []
    if not isinstance(raw, dict):
        return []
    return sanitize_tags(list(raw.get("merchant_aliases") or []) + list(raw.get("tags") or []))


def bill_row(
    bill: Bill,
    embedding: list[float],
    category_id: Optional[str],
    tags: tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    """Map a Bill to the ``bills`` table columns (per migrations 001/004)."""
    return {
        "tags": ", ".join(tags) or None,
        "merchant": _val(bill.merchant),
        "merchant_provenance": _prov(bill.merchant),
        "merchant_source_ref": _ref(bill.merchant),
        "merchant_confidence": bill.merchant.confidence if bill.merchant else None,
        "bill_type": bill.bill_type.value,
        "bill_date": _val(bill.bill_date),
        "bill_date_provenance": _prov(bill.bill_date),
        "bill_date_source_ref": _ref(bill.bill_date),
        "bill_date_confidence": bill.bill_date.confidence if bill.bill_date else None,
        "currency": bill.currency,
        "subtotal": _num(bill.subtotal),
        "tax_rate": _num(bill.tax_rate),
        "tax_base": _num(bill.tax_base),
        "tax_amount": _num(bill.tax_amount),
        "total_amount": _num(bill.total_amount),
        "total_provenance": _prov(bill.total_amount),
        "total_source_ref": _ref(bill.total_amount),
        "total_confidence": bill.total_amount.confidence if bill.total_amount else None,
        "category_id": category_id,
        "category_provenance": (bill.category and "user_provided") or None,
        "layout_supported": bill.layout_supported,
        "nothing_to_verify": bill.nothing_to_verify,
        "status": "saved",
        # pgvector accepts the bracketed string form via PostgREST.
        "embedding": vector_literal(embedding),
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }


def line_item_rows(bill_id: str, bill: Bill) -> list[dict[str, Any]]:
    rows = []
    for item in bill.line_items:
        rows.append(
            {
                "bill_id": bill_id,
                "position": item.position,
                "description": _val(item.description),
                "description_provenance": _prov(item.description),
                "description_source_ref": _ref(item.description),
                "description_confidence": item.description.confidence if item.description else None,
                "quantity": _num(item.quantity),
                "unit_amount": _num(item.unit_amount),
                "line_total": _num(item.line_total),
                "line_total_provenance": _prov(item.line_total),
                "line_total_source_ref": _ref(item.line_total),
                "line_total_confidence": item.line_total.confidence if item.line_total else None,
            }
        )
    return rows


def tax_line_rows(bill_id: str, bill: Bill) -> list[dict[str, Any]]:
    """Map the named tax breakdown to ``tax_lines`` rows (migration 005)."""
    rows = []
    for pos, tl in enumerate(bill.tax_lines):
        rows.append(
            {
                "bill_id": bill_id,
                "position": pos,
                "name": tl.name,
                "rate": _num(tl.rate),
                "amount": _num(tl.amount),
                "amount_provenance": _prov(tl.amount),
                "amount_source_ref": _ref(tl.amount),
                "amount_confidence": tl.amount.confidence if tl.amount else None,
            }
        )
    return rows


def flag_rows(bill_id: str, bill: Bill) -> list[dict[str, Any]]:
    return [
        {
            "bill_id": bill_id,
            "kind": f.kind.value,
            "conflicting_figures": f.conflicting_figures,
            "explanation_text": f.explanation_text,
        }
        for f in bill.discrepancies
    ]


def explanation_row(bill_id: str, bill: Bill) -> Optional[dict[str, Any]]:
    if not bill.explanation:
        return None
    return {
        "bill_id": bill_id,
        "bill_summary": bill.explanation.bill_summary,
        "line_explanations": bill.explanation.line_explanations,
    }


def artifact_rows(bill_id: str, bill: Bill) -> list[dict[str, Any]]:
    return [
        {
            "bill_id": bill_id,
            "kind": a.kind.value,
            "storage_path": a.storage_path,
            "page_order": a.page_order,
            "raw_text": a.raw_text,
            "quality_score": a.quality_score,
        }
        for a in bill.source_artifacts
    ]


# --- IO ---------------------------------------------------------------------


def _resolve_category_id(bill: Bill, db) -> Optional[str]:
    if not bill.category:
        return None
    if bill.category.id:
        return str(bill.category.id)
    # Resolve by name against the seeded/controlled list (creation is out of scope).
    matches = db.select("categories", {"name": bill.category.name})
    return matches[0]["id"] if matches else None


def save_bill(
    bill: Bill,
    original_files: Optional[list[tuple[bytes, str, str]]] = None,
    *,
    db=persistence,
    embed_fn: Callable[[str], list[float]] = _default_embed,
    llm=None,
) -> dict[str, Any]:
    """Persist a reviewed bill as the canonical record; return the saved row.

    Uploads any provided original files to private Storage and records them as
    source_artifacts (supports the privacy/traceability claim). Reuses the same
    embedding rendering as every other caller. When an ``llm`` is provided,
    best-effort search tags are generated and folded into the embedding.
    """
    # Upload originals (best-effort within the trust boundary).
    for content, filename, content_type in original_files or []:
        path = db.upload_artifact(content, filename, content_type)
        kind = (
            "pdf"
            if (content_type == "application/pdf" or filename.lower().endswith(".pdf"))
            else "image"
        )
        from src.models import ArtifactKind, SourceArtifact

        bill.source_artifacts.append(
            SourceArtifact(
                kind=ArtifactKind(kind), storage_path=path, page_order=len(bill.source_artifacts)
            )
        )

    tags = enrichment_tags(bill, llm)
    embedding = embed_fn(embedding_text(bill, tags))
    category_id = _resolve_category_id(bill, db)

    saved = db.insert_row("bills", bill_row(bill, embedding, category_id, tags))
    bill_id = saved["id"]

    for row in line_item_rows(bill_id, bill):
        db.insert_row("line_items", row)
    for row in tax_line_rows(bill_id, bill):
        db.insert_row("tax_lines", row)
    for row in flag_rows(bill_id, bill):
        db.insert_row("discrepancy_flags", row)
    expl = explanation_row(bill_id, bill)
    if expl:
        db.insert_row("explanations", expl)
    for row in artifact_rows(bill_id, bill):
        db.insert_row("source_artifacts", row)

    return saved

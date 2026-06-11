"""Bill ingestion API.

`POST /bills:process` runs the deterministic extraction pipeline and returns a
non-persisted structured candidate. Non-bill / unreadable input is declined with
HTTP 422 and no fabricated fields (FR-021). Discrepancy checks (Phase 4),
explanation (Phase 5), category suggestion and save (Phase 6) are layered onto
this router in later phases.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile as StarletteUploadFile

from src.models import (
    Bill,
    BillType,
    Category,
    DiscrepancyFlag,
    DiscrepancyKind,
    Explanation,
    LineItem,
    Provenance,
    SourceRef,
    TracedValue,
)
from src.services import persistence
from src.services.bill_writer import save_bill
from src.services.category_service import suggest_category
from src.services.discrepancy_service import detect as detect_discrepancies
from src.services.explanation import build_explanation
from src.services.extraction import NotABillError, process_inputs
from src.services.persistence import PersistenceError

logger = logging.getLogger("billology.bills")
router = APIRouter(tags=["bills"])


def _clean_str(value: object) -> Optional[str]:
    """Return a non-empty string from a form value, else None."""
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


@router.post("/bills:process", response_model=Bill)
async def process_bill(request: Request):
    """Extract a structured candidate from an image, PDF, or pasted text.

    The multipart form is read directly so that a blank/empty ``files`` field
    (which the mobile client may send on text-only or PDF-only submissions) is
    treated as "no files provided" rather than triggering UploadFile validation.
    """
    form = await request.form()

    payload: list[tuple[bytes, str, str]] = []
    for value in form.getlist("files"):
        # Keep only genuine uploaded file parts; ignore empty-string placeholders.
        if isinstance(value, StarletteUploadFile):
            content = await value.read()
            if content:
                payload.append(
                    (content, value.filename or "upload", value.content_type or "")
                )

    text = _clean_str(form.get("text"))
    bill_type_hint = _clean_str(form.get("bill_type_hint"))

    try:
        candidate = process_inputs(
            files=payload or None, text=text, bill_type_hint=bill_type_hint
        )
    except NotABillError as exc:
        return JSONResponse(status_code=422, content={"declined": True, "reason": exc.reason})

    # Deterministic discrepancy detection over the candidate (Phase 4 / US4).
    candidate.discrepancies = detect_discrepancies(candidate)
    # Plain-language explanation from extracted data only (Phase 5 / US3).
    candidate.explanation = build_explanation(candidate)
    # Suggested category from the controlled list (Phase 6 / US6).
    candidate.category = Category(name=suggest_category(candidate))
    return candidate


# --- POST /bills (save) -----------------------------------------------------

@router.post("/bills", response_model=Bill, status_code=201)
async def save_reviewed_bill(request: Request):
    """Persist a reviewed/corrected candidate as the canonical record (US5).

    Accepts the reviewed candidate as a JSON ``candidate`` field plus the
    optional original ``files`` (re-sent so the originals can be archived to
    private Storage). Edited fields must arrive already marked
    ``provenance=user_provided`` by the client (FR-004).
    """
    form = await request.form()
    raw = form.get("candidate")
    if not isinstance(raw, str) or not raw.strip():
        raise HTTPException(status_code=422, detail="Missing 'candidate' JSON")

    try:
        bill = Bill.model_validate_json(raw)
    except Exception as exc:  # noqa: BLE001 - surface a clean 422
        raise HTTPException(status_code=422, detail=f"Invalid candidate: {exc}") from exc

    originals: list[tuple[bytes, str, str]] = []
    for value in form.getlist("files"):
        if isinstance(value, StarletteUploadFile):
            content = await value.read()
            if content:
                originals.append(
                    (content, value.filename or "upload", value.content_type or "")
                )

    try:
        saved = save_bill(bill, original_files=originals or None)
    except PersistenceError as exc:
        # Surface the real DB failure instead of a generic 500 / false success.
        logger.error("save_bill failed: %s", exc)
        return JSONResponse(status_code=502, content={"error": "persist_failed", "detail": str(exc)})
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error saving bill")
        return JSONResponse(status_code=500, content={"error": "save_error", "detail": str(exc)})

    bill_id = saved.get("id")
    if not bill_id:
        # Never claim success without a real persisted row id.
        return JSONResponse(
            status_code=502,
            content={"error": "persist_failed", "detail": "Insert returned no id."},
        )
    bill.id = bill_id
    bill.status = "saved"
    return bill


# --- GET /bills/{id} --------------------------------------------------------

def _traced(value, provenance=None, source_ref=None, confidence=None) -> Optional[TracedValue]:
    if value is None:
        return None
    ref = SourceRef(**source_ref) if isinstance(source_ref, dict) else None
    return TracedValue(
        value=str(value),
        provenance=Provenance(provenance) if provenance else Provenance.extracted,
        confidence=confidence,
        source_ref=ref,
    )


def _bill_from_rows(row: dict, items: list[dict], flags: list[dict],
                    explanation: Optional[dict], category: Optional[dict]) -> Bill:
    """Reconstruct a canonical Bill from persisted rows (columns per migration)."""
    line_items = [
        LineItem(
            id=li.get("id"),
            position=li.get("position", idx),
            description=_traced(
                li.get("description"), li.get("description_provenance"),
                li.get("description_source_ref"), li.get("description_confidence"),
            ) or TracedValue(value=""),
            quantity=_traced(li.get("quantity")),
            unit_amount=_traced(li.get("unit_amount")),
            line_total=_traced(
                li.get("line_total"), li.get("line_total_provenance"),
                li.get("line_total_source_ref"), li.get("line_total_confidence"),
            ) or TracedValue(value="0"),
        )
        for idx, li in enumerate(sorted(items, key=lambda r: r.get("position", 0)))
    ]

    return Bill(
        id=row.get("id"),
        merchant=_traced(
            row.get("merchant"), row.get("merchant_provenance"),
            row.get("merchant_source_ref"), row.get("merchant_confidence"),
        ) or TracedValue(value=None),
        bill_type=BillType(row.get("bill_type", "unsupported")),
        bill_date=_traced(
            row.get("bill_date"), row.get("bill_date_provenance"),
            row.get("bill_date_source_ref"), row.get("bill_date_confidence"),
        ),
        currency=row.get("currency", "INR"),
        subtotal=_traced(row.get("subtotal")),
        tax_rate=_traced(row.get("tax_rate")),
        tax_base=_traced(row.get("tax_base")),
        tax_amount=_traced(row.get("tax_amount")),
        total_amount=_traced(
            row.get("total_amount"), row.get("total_provenance"),
            row.get("total_source_ref"), row.get("total_confidence"),
        ) or TracedValue(value="0"),
        category=(
            Category(id=category.get("id"), name=category.get("name"),
                     is_seeded=category.get("is_seeded", False))
            if category else None
        ),
        line_items=line_items,
        discrepancies=[
            DiscrepancyFlag(
                kind=DiscrepancyKind(f["kind"]),
                conflicting_figures=f.get("conflicting_figures", {}),
                explanation_text=f.get("explanation_text", ""),
            )
            for f in flags
        ],
        explanation=(
            Explanation(
                bill_summary=explanation.get("bill_summary", ""),
                line_explanations=explanation.get("line_explanations", {}),
            )
            if explanation else None
        ),
        layout_supported=row.get("layout_supported", True),
        nothing_to_verify=row.get("nothing_to_verify", False),
        status=row.get("status", "saved"),
    )


@router.get("/bills/{bill_id}", response_model=Bill)
def get_bill(bill_id: str):
    """Return one saved canonical bill — the record all features read from."""
    rows = persistence.select("bills", {"id": bill_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Bill not found")
    row = rows[0]
    items = persistence.select("line_items", {"bill_id": bill_id})
    flags = persistence.select("discrepancy_flags", {"bill_id": bill_id})
    expl_rows = persistence.select("explanations", {"bill_id": bill_id})
    explanation = expl_rows[0] if expl_rows else None
    category = None
    if row.get("category_id"):
        cat_rows = persistence.select("categories", {"id": row["category_id"]})
        category = cat_rows[0] if cat_rows else None
    return _bill_from_rows(row, items, flags, explanation, category)

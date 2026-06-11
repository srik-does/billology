"""Build a plain-language Explanation for a bill (US3 / FR-007).

The LLM is given ONLY descriptions (merchant, bill type, line-item descriptions)
— never amounts — and is told not to emit any numbers. Every figure the user
sees comes from the structured record, not from this text (Principle I).

If the LLM is unavailable (no key / offline / error), a deterministic fallback
keeps the pipeline working so the demo never blocks on the model.
"""

from __future__ import annotations

from typing import Optional

from src.models import Bill, Explanation
from src.services.llm_service import LLMService, get_llm_service


def _payload(bill: Bill) -> dict:
    return {
        "merchant": bill.merchant.value,
        "bill_type": bill.bill_type.value,
        "line_items": [
            {"position": item.position, "description": item.description.value}
            for item in bill.line_items
        ],
    }


def _fallback(bill: Bill) -> tuple[str, dict[str, str]]:
    merchant = bill.merchant.value or "This bill"
    n = len(bill.line_items)
    if bill.nothing_to_verify or n == 0:
        summary = f"{merchant}: a single total with no itemized breakdown."
    else:
        summary = f"{merchant}: {n} item{'s' if n != 1 else ''} charged."
    line = {str(item.position): (item.description.value or "Charge") for item in bill.line_items}
    return summary, line


def build_explanation(bill: Bill, llm: Optional[LLMService] = None) -> Explanation:
    """Return an Explanation, using the LLM when available, else a fallback."""
    try:
        service = llm or get_llm_service()
        raw = service.explain(_payload(bill))
        summary = str(raw.get("bill_summary") or "").strip()
        line_raw = raw.get("line_explanations")
        if not isinstance(line_raw, dict):
            line_raw = {}

        line = {}
        for item in bill.line_items:
            key = str(item.position)
            text = line_raw.get(key)
            if text is None:
                text = line_raw.get(item.position)  # tolerate int keys
            line[key] = str(text).strip() if text else (item.description.value or "Charge")

        if not summary:
            summary, _ = _fallback(bill)
        return Explanation(bill_summary=summary, line_explanations=line)
    except Exception:
        summary, line = _fallback(bill)
        return Explanation(bill_summary=summary, line_explanations=line)

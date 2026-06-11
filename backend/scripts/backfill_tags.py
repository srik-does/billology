"""Backfill search tags + re-embed existing saved bills (Ask reliability).

Run once after applying migration 004 (and again if the embedding rendering or
enrichment prompt changes):

    venv\\Scripts\\python.exe backend\\scripts\\backfill_tags.py [--dry-run]

For each saved bill: generate descriptive tags/aliases via the server's
configured LLM (best-effort), rebuild the canonical embedding text including
the tags, and update the row. Figures are never touched (Principle I).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models import Bill, BillType, Category, LineItem, TracedValue
from src.services import persistence
from src.services.bill_writer import embedding_text, enrichment_tags, vector_literal
from src.services.embedding_service import embed


def _as_bill(row: dict, items: list[dict], category_name: str | None) -> Bill:
    """Lightweight Bill carrying only the descriptive fields the enrichment
    payload and embedding text read (figures are irrelevant here)."""
    try:
        bill_type = BillType(row.get("bill_type"))
    except ValueError:
        bill_type = BillType.unsupported
    return Bill(
        merchant=TracedValue(value=row.get("merchant")),
        bill_type=bill_type,
        category=Category(name=category_name) if category_name else None,
        total_amount=TracedValue(),
        line_items=[
            LineItem(
                position=i,
                description=TracedValue(value=item.get("description")),
                line_total=TracedValue(),
            )
            for i, item in enumerate(items)
            if item.get("description")
        ],
    )


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    try:
        from src.services.llm_service import get_llm_service

        llm = get_llm_service()
    except Exception as exc:  # noqa: BLE001
        print(f"No LLM available ({exc}); bills will be re-embedded without tags.")
        llm = None

    categories = {c["id"]: c.get("name") for c in persistence.select("categories")}
    items_by_bill: dict[str, list[dict]] = {}
    for item in persistence.select("line_items"):
        items_by_bill.setdefault(item.get("bill_id"), []).append(item)

    bills = [b for b in persistence.select("bills") if b.get("status") == "saved"]
    print(f"Backfilling {len(bills)} saved bill(s){' (dry run)' if dry_run else ''}…")

    for row in bills:
        bill = _as_bill(
            row,
            sorted(items_by_bill.get(row["id"], []), key=lambda i: i.get("position") or 0),
            categories.get(row.get("category_id")),
        )
        tags = enrichment_tags(bill, llm)
        text = embedding_text(bill, tags)
        print(f"  {row.get('merchant') or '(no merchant)'}: tags={tags}")
        if dry_run:
            continue
        persistence.update_rows(
            "bills",
            {"id": row["id"]},
            {"tags": ", ".join(tags) or None, "embedding": vector_literal(embed(text))},
        )

    print("Done." if not dry_run else "Dry run complete — no rows written.")


if __name__ == "__main__":
    main()

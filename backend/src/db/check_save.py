"""Diagnostic: perform ONE real save against the configured Supabase and report.

Run from backend/ with .env configured:
    python -m src.db.check_save

Prints the bills count before/after, the saved row id, and the embedding literal
format — or the full error if the insert fails. Use this to confirm rows actually
land in the `bills` table (the "201 but nothing persisted" investigation).
"""

from __future__ import annotations

import traceback

from src.config import get_settings
from src.db.seed_demo_bills import build_demo_bills
from src.services import bill_writer, persistence


def main() -> None:
    settings = get_settings()
    print(
        f"SUPABASE_URL set: {bool(settings.supabase_url)} | key set: {bool(settings.supabase_key)}"
    )
    print(f"key prefix: {settings.supabase_key[:8] + '…' if settings.supabase_key else '(none)'}")

    bill = build_demo_bills()[0]  # one telecom recharge

    try:
        before = len(persistence.select("bills"))
        print(f"bills count BEFORE: {before}")

        # Show the embedding literal we will send (first chars), to verify format.
        emb = bill_writer._default_embed(bill_writer.embedding_text(bill))
        literal = bill_writer.vector_literal(emb)
        print(f"embedding dims: {len(emb)} | literal head: {literal[:40]}…")

        saved = bill_writer.save_bill(bill)
        print(f"save_bill returned id: {saved.get('id')!r}")

        after = len(persistence.select("bills"))
        print(f"bills count AFTER: {after}")
        print("RESULT:", "PERSISTED ✅" if after > before else "NOT PERSISTED ❌ (no new row)")
    except Exception:  # noqa: BLE001 - this is a diagnostic; show everything
        print("RESULT: ERROR ❌ — full traceback follows:\n")
        traceback.print_exc()


if __name__ == "__main__":
    main()

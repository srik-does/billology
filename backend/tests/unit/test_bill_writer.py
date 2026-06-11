"""bill_writer: embedding-text rendering, column mapping, and save orchestration.

Uses a fake DB + embed fn so the canonical-write path is exercised without a
live Supabase — the same path the seed script (T034) will reuse.
"""

from __future__ import annotations

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
from src.services import bill_writer


def _tv(v, prov=Provenance.extracted, conf=None, line=None):
    return TracedValue(
        value=v, provenance=prov, confidence=conf,
        source_ref=SourceRef(line=line) if line is not None else None,
    )


def _bill():
    return Bill(
        merchant=_tv("FreshMart", conf=0.95, line=0),
        bill_type=BillType.grocery,
        category=Category(name="Groceries"),
        total_amount=_tv("160.00", line=5),
        subtotal=_tv("160.00"),
        line_items=[
            LineItem(position=0, description=_tv("Tomatoes"), line_total=_tv("40.00")),
            LineItem(position=1, description=_tv("Milk"), line_total=_tv("120.00")),
        ],
        discrepancies=[
            DiscrepancyFlag(kind=DiscrepancyKind.sum_mismatch, conflicting_figures={"a": "1"}, explanation_text="x")
        ],
        explanation=Explanation(bill_summary="A grocery bill", line_explanations={"0": "veg"}),
    )


class _FakeDB:
    def __init__(self):
        self.inserts: list[tuple[str, dict]] = []

    def select(self, table, filters=None):
        if table == "categories" and filters and filters.get("name") == "Groceries":
            return [{"id": "cat-groceries", "name": "Groceries"}]
        return []

    def insert_row(self, table, row):
        self.inserts.append((table, row))
        return {"id": f"{table}-id", **row}

    def upload_artifact(self, content, filename, content_type):
        return f"bucket/{filename}"


def test_embedding_text_is_descriptive_and_deterministic():
    text = bill_writer.embedding_text(_bill())
    assert text == "FreshMart | grocery | Groceries | Tomatoes | Milk"


def test_embedding_text_appends_enrichment_tags():
    text = bill_writer.embedding_text(_bill(), ["fresh mart", "kirana"])
    assert text.endswith("Tomatoes | Milk | fresh mart | kirana")


def test_sanitize_tags_bounds_and_filters():
    raw = ["Kirana", "kirana", 42, "  Fresh   Mart ", "12345", "x" * 41, ""]
    assert bill_writer.sanitize_tags(raw) == ["kirana", "fresh mart"]
    assert bill_writer.sanitize_tags("not-a-list") == []
    assert len(bill_writer.sanitize_tags([f"tag{i}" for i in range(50)])) == 24


def test_save_bill_with_llm_persists_tags_and_embeds_them():
    class _FakeLLM:
        def enrich_bill(self, payload):
            assert "items" in payload and "merchant" in payload
            return {"tags": ["kirana"], "merchant_aliases": ["fresh-mart"]}

    db = _FakeDB()
    embedded: list[str] = []

    def _embed(text):
        embedded.append(text)
        return [0.0] * 384

    bill_writer.save_bill(_bill(), db=db, embed_fn=_embed, llm=_FakeLLM())
    bills_row = next(r for t, r in db.inserts if t == "bills")
    assert bills_row["tags"] == "fresh-mart, kirana"
    assert "kirana" in embedded[0]


def test_save_bill_without_llm_has_no_tags():
    db = _FakeDB()
    bill_writer.save_bill(_bill(), db=db, embed_fn=lambda t: [0.0] * 384)
    bills_row = next(r for t, r in db.inserts if t == "bills")
    assert bills_row["tags"] is None


def test_bill_row_maps_columns_and_embedding():
    row = bill_writer.bill_row(_bill(), [0.1, 0.2, 0.3], "cat-groceries")
    assert row["merchant"] == "FreshMart"
    assert row["merchant_provenance"] == "extracted"
    assert row["merchant_confidence"] == 0.95
    assert row["total_amount"] == "160.00"
    assert row["category_id"] == "cat-groceries"
    assert row["status"] == "saved"
    assert row["embedding"] == "[0.1,0.2,0.3]"  # pgvector string form


def test_save_bill_inserts_parent_then_children_and_resolves_category():
    db = _FakeDB()
    saved = bill_writer.save_bill(_bill(), db=db, embed_fn=lambda t: [0.0] * 384)
    tables = [t for t, _ in db.inserts]
    assert tables[0] == "bills"  # parent first
    assert tables.count("line_items") == 2
    assert "discrepancy_flags" in tables
    assert "explanations" in tables
    assert saved["id"] == "bills-id"
    # category resolved by name -> id
    bills_row = next(r for t, r in db.inserts if t == "bills")
    assert bills_row["category_id"] == "cat-groceries"


def test_save_bill_uploads_originals_as_artifacts():
    db = _FakeDB()
    bill_writer.save_bill(
        _bill(),
        original_files=[(b"bytes", "bill.pdf", "application/pdf")],
        db=db,
        embed_fn=lambda t: [0.0] * 384,
    )
    artifacts = [r for t, r in db.inserts if t == "source_artifacts"]
    assert len(artifacts) == 1
    assert artifacts[0]["storage_path"] == "bucket/bill.pdf"
    assert artifacts[0]["kind"] == "pdf"

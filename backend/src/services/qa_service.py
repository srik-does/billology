"""Dual-path grounded Q&A (US9 / FR-018, Principle VI).

Numeric path: derive a constrained query *intent* (category / month / aggregate),
run a safe allowlisted query, and compute the figure in deterministic Decimal code
over the returned rows. The LLM never authors SQL and never computes the number.

Semantic path: embed the question locally, retrieve real saved rows via the
match_bills pgvector RPC, and (optionally) summarize over those rows only.

Anything we can't answer from saved records returns an explicit "not available" —
never an estimate.

Routing is heuristic-first (works without a Groq key); the LLM is an optional
enhancement for the semantic summary.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Optional

from src.services import persistence

# Map keyword hints in the question to a controlled category name.
_CATEGORY_HINTS = [
    ("recharge", "Telecom/Recharge"),
    ("telecom", "Telecom/Recharge"),
    ("mobile", "Telecom/Recharge"),
    ("grocer", "Groceries"),
    ("utilit", "Utilities"),
    ("electric", "Utilities"),
    ("food", "Food & Dining"),
    ("dining", "Food & Dining"),
    ("restaurant", "Food & Dining"),
    ("shopping", "Shopping"),
]

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_NUMERIC_TRIGGERS = (
    "how much", "how many", "total", "spend", "spent", "sum", "count",
    "number of", "last time", "latest", "most recent", "average", "avg",
)


def _to_decimal(v) -> Decimal:
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _classify(question: str) -> str:
    q = question.lower()
    return "numeric" if any(t in q for t in _NUMERIC_TRIGGERS) else "semantic"


def _intent(question: str) -> dict[str, Any]:
    q = question.lower()
    category = next((name for hint, name in _CATEGORY_HINTS if hint in q), None)
    month = next((num for token, num in _MONTHS.items() if re.search(rf"\b{token}", q)), None)
    if any(w in q for w in ("last time", "latest", "most recent")):
        aggregate = "latest"
    elif any(w in q for w in ("how many", "count", "number of")):
        aggregate = "count"
    else:
        aggregate = "sum"
    return {"category": category, "month": month, "aggregate": aggregate}


def _load_bills(db) -> list[dict[str, Any]]:
    """Fetch saved bills with their category name resolved (single small dataset)."""
    cats = {c["id"]: c.get("name") for c in db.select("categories")}
    rows = []
    for b in db.select("bills"):
        if b.get("status") and b["status"] != "saved":
            continue
        rows.append(
            {
                "id": b.get("id"),
                "merchant": b.get("merchant"),
                "bill_date": b.get("bill_date"),
                "total_amount": b.get("total_amount"),
                "category": cats.get(b.get("category_id")),
            }
        )
    return rows


def _summary(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "merchant": row.get("merchant"),
        "bill_date": row.get("bill_date"),
        "total_amount": str(row.get("total_amount")) if row.get("total_amount") is not None else None,
        "category": row.get("category"),
    }


def _unanswerable(reason: str = "I don't have that information in your saved bills.") -> dict:
    return {"path": "unanswerable", "answer": reason, "records": [], "executed_query": None}


def _numeric(question: str, db) -> dict:
    intent = _intent(question)
    rows = _load_bills(db)

    if intent["category"]:
        rows = [r for r in rows if (r["category"] or "").lower() == intent["category"].lower()]
    if intent["month"]:
        rows = [r for r in rows if _month_of(r["bill_date"]) == intent["month"]]

    if not rows:
        return _unanswerable()

    cat = intent["category"] or "all categories"
    when = f" in month {intent['month']:02d}" if intent["month"] else ""
    desc = f"{intent['aggregate']}(total_amount) WHERE category={cat}{when}"

    if intent["aggregate"] == "latest":
        latest = max(rows, key=lambda r: (r["bill_date"] or ""))
        answer = (
            f"Your most recent {cat} bill was ₹{latest['total_amount']} "
            f"on {latest['bill_date']} ({latest['merchant']})."
        )
        return {"path": "numeric", "answer": answer, "records": [_summary(latest)], "executed_query": desc}

    if intent["aggregate"] == "count":
        return {
            "path": "numeric",
            "answer": f"You have {len(rows)} {cat} bill(s){when}.",
            "records": [_summary(r) for r in rows],
            "executed_query": desc,
        }

    total = sum((_to_decimal(r["total_amount"]) for r in rows), Decimal("0"))
    return {
        "path": "numeric",
        "answer": f"You spent ₹{total} on {cat}{when} across {len(rows)} bill(s).",
        "records": [_summary(r) for r in rows],
        "executed_query": desc,
    }


def _month_of(bill_date) -> Optional[int]:
    if not bill_date:
        return None
    m = re.match(r"\d{4}-(\d{2})", str(bill_date))
    return int(m.group(1)) if m else None


def _semantic(question: str, db, embed_fn, llm, k: int = 5) -> dict:
    if embed_fn is None:
        return _unanswerable("Semantic search is unavailable (no embedding model).")
    from src.services.bill_writer import vector_literal

    vec = vector_literal(embed_fn(question))
    matches = db.match_bills(vec, k)
    if not matches:
        return _unanswerable()

    # The match_bills RPC returns category_id (uuid) but not the category name;
    # resolve names so retrieved records carry their category (not null).
    cat_names = {c["id"]: c.get("name") for c in db.select("categories")}
    for m in matches:
        m["category"] = cat_names.get(m.get("category_id"))

    records = [_summary(m) for m in matches]
    answer = None
    if llm is not None:
        try:
            answer = llm.summarize_results(question, records)
        except Exception:
            answer = None
    if not answer:
        merchants = ", ".join(m["merchant"] for m in matches if m.get("merchant"))
        answer = f"Found {len(matches)} matching bill(s): {merchants}."
    return {"path": "semantic", "answer": answer, "records": records, "executed_query": None}


def answer_question(
    question: str,
    *,
    db=persistence,
    embed_fn: Optional[Callable[[str], list[float]]] = None,
    llm=None,
) -> dict:
    question = (question or "").strip()
    if not question:
        return _unanswerable("Please ask a question about your spending.")
    if _classify(question) == "numeric":
        return _numeric(question, db)
    return _semantic(question, db, embed_fn, llm)

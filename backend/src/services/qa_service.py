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
from difflib import SequenceMatcher
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


# Numeric answers are code-generated template strings; translate the templates
# (the figures themselves are computed, never translated).
_TEMPLATES = {
    "en": {
        "sum": "You spent ₹{total} on {cat}{who}{when} across {n} bill(s).",
        "count": "You have {n} {cat} bill(s){who}{when}.",
        "average": "Your average {cat} bill{who}{when} is ₹{avg} (over {n} bill(s)).",
        "latest": "Your most recent {cat} bill was ₹{amount} on {date} ({merchant}).",
        "unanswerable": "I don't have that information in your saved bills.",
        "ask": "Please ask a question about your spending.",
    },
    "hi": {
        "sum": "आपने {cat}{who}{when} पर {n} बिल में कुल ₹{total} खर्च किए।",
        "count": "आपके पास {cat}{who}{when} के {n} बिल हैं।",
        "average": "आपका औसत {cat} बिल{who}{when} ₹{avg} है ({n} बिल पर)।",
        "latest": "आपका सबसे हालिया {cat} बिल ₹{amount} था, {date} को ({merchant})।",
        "unanswerable": "आपके सहेजे गए बिलों में यह जानकारी उपलब्ध नहीं है।",
        "ask": "कृपया अपने खर्च के बारे में कोई प्रश्न पूछें।",
    },
    "te": {
        "sum": "మీరు {cat}{who}{when} పై {n} బిల్లులలో మొత్తం ₹{total} ఖర్చు చేశారు.",
        "count": "మీ వద్ద {cat}{who}{when} బిల్లులు {n} ఉన్నాయి.",
        "average": "మీ సగటు {cat} బిల్లు{who}{when} ₹{avg} ({n} బిల్లులపై).",
        "latest": "మీ ఇటీవలి {cat} బిల్లు ₹{amount}, {date} న ({merchant}).",
        "unanswerable": "మీ సేవ్ చేసిన బిల్లులలో ఆ సమాచారం లేదు.",
        "ask": "దయచేసి మీ ఖర్చు గురించి ప్రశ్న అడగండి.",
    },
}


def _t(key: str) -> str:
    from src.services.request_context import language

    return _TEMPLATES.get(language.get(), _TEMPLATES["en"]).get(key, _TEMPLATES["en"][key])


def _classify(question: str) -> str:
    q = question.lower()
    return "numeric" if any(t in q for t in _NUMERIC_TRIGGERS) else "semantic"


# --- forgiving matching -------------------------------------------------------

def _norm(s: str) -> str:
    """Collapse to lowercase alphanumerics so 'D-Mart' == 'd mart' == 'DMART'."""
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _fuzzy_merchant(needle: str, merchant: str) -> bool:
    """Spelling/punctuation-tolerant merchant match (fixes the 'small change in
    search keys → No bills found' cliff)."""
    a, b = _norm(needle), _norm(merchant)
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    return SequenceMatcher(None, a, b, autojunk=False).ratio() >= 0.8


# Question words that carry no retrieval signal.
_STOPWORDS = frozenset(
    "the a an my i me of on in at for to from did do was is are and or with "
    "how much many what where when which who show find get all any bill bills "
    "spend spent spending buy bought purchase purchased paid pay last this "
    "that month year time recent latest total amount".split()
)


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (s or "").lower())
            if len(t) >= 3 and t not in _STOPWORDS}


def _keyword_score(question_tokens: set[str], row_text: str) -> int:
    """Count question tokens that hit the row's descriptive text (tolerating
    joined/split words: 'dmart' hits 'd mart' and vice versa)."""
    row_tokens = _tokens(row_text)
    joined = _norm(row_text)
    score = 0
    for qt in question_tokens:
        if qt in row_tokens or (len(qt) >= 4 and qt in joined):
            score += 1
    return score


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
    return {"category": category, "month": month, "merchant": None, "aggregate": aggregate}


def _llm_intent(question: str, db, llm) -> Optional[dict[str, Any]]:
    """LLM translates the question; every field is validated/allowlisted here.

    The LLM picks WHICH filters apply (Principle VI: question → query); it never
    computes the figure. Returns None on any failure → heuristic fallback.
    """
    if llm is None:
        return None
    try:
        from datetime import date

        cats = [c.get("name") for c in db.select("categories") if c.get("name")]
        raw = llm.derive_intent(question, cats, date.today().isoformat())
    except Exception:  # noqa: BLE001 - LLM optional
        return None
    if not isinstance(raw, dict):
        return None

    path = raw.get("path")
    if path not in ("numeric", "semantic"):
        return None
    category = raw.get("category")
    if not (isinstance(category, str) and category in cats):
        category = None
    month = raw.get("month")
    if not (isinstance(month, str) and re.fullmatch(r"\d{4}-\d{2}", month)):
        month = None
    merchant = raw.get("merchant")
    merchant = merchant.strip() if isinstance(merchant, str) and 0 < len(merchant.strip()) <= 60 else None
    aggregate = raw.get("aggregate")
    if aggregate not in ("sum", "count", "latest", "average"):
        aggregate = "sum"
    return {
        "path": path,
        "category": category,
        "month": month,
        "merchant": merchant,
        "aggregate": aggregate,
    }


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
                "tags": b.get("tags"),
            }
        )
    return rows


def _searchable_text(row: dict[str, Any], items_by_bill: dict[Any, list[str]]) -> str:
    """All descriptive text for keyword matching: merchant, category, tags, items."""
    parts = [row.get("merchant") or "", row.get("category") or "", row.get("tags") or ""]
    parts.extend(items_by_bill.get(row.get("id"), []))
    return " ".join(parts)


def _load_item_descriptions(db) -> dict[Any, list[str]]:
    by_bill: dict[Any, list[str]] = {}
    for item in db.select("line_items"):
        desc = item.get("description")
        if desc:
            by_bill.setdefault(item.get("bill_id"), []).append(desc)
    return by_bill


def _summary(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "merchant": row.get("merchant"),
        "bill_date": row.get("bill_date"),
        "total_amount": str(row.get("total_amount")) if row.get("total_amount") is not None else None,
        "category": row.get("category"),
    }


def _unanswerable(reason: Optional[str] = None) -> dict:
    return {
        "path": "unanswerable",
        "answer": reason or _t("unanswerable"),
        "records": [],
        "executed_query": None,
    }


def _apply_filters(intent: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if intent["category"]:
        rows = [r for r in rows if (r["category"] or "").lower() == intent["category"].lower()]
    if intent["month"] is not None:
        if isinstance(intent["month"], int):  # heuristic path: bare month number
            rows = [r for r in rows if _month_of(r["bill_date"]) == intent["month"]]
        else:  # LLM path: "YYYY-MM"
            rows = [r for r in rows if str(r["bill_date"] or "").startswith(intent["month"])]
    if intent.get("merchant"):
        needle = intent["merchant"]
        rows = [r for r in rows if _fuzzy_merchant(needle, r["merchant"] or "")
                or _keyword_score(_tokens(needle), r.get("tags") or "") > 0]
    return rows


def _numeric(question: str, db, intent: Optional[dict[str, Any]] = None) -> dict:
    intent = intent or _intent(question)
    all_rows = _load_bills(db)
    rows = _apply_filters(intent, all_rows)

    # A named merchant is the precise filter; a guessed category must not zero
    # it out (e.g. "DMart" guessed as Shopping when its bills are Groceries).
    if not rows and intent.get("merchant") and intent["category"]:
        intent = {**intent, "category": None}
        rows = _apply_filters(intent, all_rows)

    if not rows:
        return _unanswerable()

    cat = intent["category"] or "all categories"
    when = f" in {intent['month']}" if intent["month"] is not None else ""
    who = f" at {intent['merchant']}" if intent.get("merchant") else ""
    desc = f"{intent['aggregate']}(total_amount) WHERE category={cat}{who}{when}"

    if intent["aggregate"] == "latest":
        latest = max(rows, key=lambda r: (r["bill_date"] or ""))
        answer = _t("latest").format(
            cat=cat, amount=latest["total_amount"], date=latest["bill_date"], merchant=latest["merchant"]
        )
        return {"path": "numeric", "answer": answer, "records": [_summary(latest)], "executed_query": desc}

    if intent["aggregate"] == "count":
        return {
            "path": "numeric",
            "answer": _t("count").format(n=len(rows), cat=cat, who=who, when=when),
            "records": [_summary(r) for r in rows],
            "executed_query": desc,
        }

    total = sum((_to_decimal(r["total_amount"]) for r in rows), Decimal("0"))
    if intent["aggregate"] == "average":
        avg = (total / len(rows)).quantize(Decimal("0.01"))
        return {
            "path": "numeric",
            "answer": _t("average").format(cat=cat, who=who, when=when, avg=avg, n=len(rows)),
            "records": [_summary(r) for r in rows],
            "executed_query": desc,
        }
    return {
        "path": "numeric",
        "answer": _t("sum").format(total=total, cat=cat, who=who, when=when, n=len(rows)),
        "records": [_summary(r) for r in rows],
        "executed_query": desc,
    }


def _month_of(bill_date) -> Optional[int]:
    if not bill_date:
        return None
    m = re.match(r"\d{4}-(\d{2})", str(bill_date))
    return int(m.group(1)) if m else None


def _semantic(question: str, db, embed_fn, llm, k: int = 5) -> dict:
    """Hybrid retrieval: vector similarity + keyword/tag matching, merged.

    Either signal alone can surface a bill, so a wording change that misses one
    path is caught by the other; works keyword-only when no embedder is set.
    """
    matches: list[dict[str, Any]] = []
    if embed_fn is not None:
        from src.services.bill_writer import vector_literal

        vec = vector_literal(embed_fn(question))
        matches = db.match_bills(vec, k)
        # The match_bills RPC returns category_id (uuid) but not the category
        # name; resolve names so retrieved records carry their category.
        cat_names = {c["id"]: c.get("name") for c in db.select("categories")}
        for m in matches:
            m["category"] = cat_names.get(m.get("category_id"))

    # Keyword pass over merchant/category/tags/item descriptions.
    question_tokens = _tokens(question)
    if question_tokens:
        all_rows = _load_bills(db)
        items_by_bill = _load_item_descriptions(db)
        seen_ids = {m.get("id") for m in matches}
        scored = sorted(
            ((row, _keyword_score(question_tokens, _searchable_text(row, items_by_bill)))
             for row in all_rows if row["id"] not in seen_ids),
            key=lambda pair: -pair[1],
        )
        matches.extend(row for row, score in scored[:k] if score > 0)

    if not matches:
        return _unanswerable()

    records = [_summary(m) for m in matches[: k + 1]]
    answer = None
    if llm is not None:
        try:
            answer = llm.summarize_results(question, records)
        except Exception:
            answer = None
    if not answer:
        merchants = ", ".join(r["merchant"] for r in records if r.get("merchant"))
        answer = f"Found {len(records)} matching bill(s): {merchants}."
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
        return _unanswerable(_t("ask"))
    # Preferred routing: LLM translates the question into a validated intent
    # (Principle VI). Heuristic keyword routing remains the no-LLM fallback.
    intent = _llm_intent(question, db, llm)
    if intent is not None:
        if intent["path"] == "numeric":
            result = _numeric(question, db, intent)
            # A named merchant that matched nothing may just be spelled
            # differently — degrade to retrieval (closest matches) instead of
            # a hard "no bills found". Category-only misses stay honest: "no
            # Utilities bills" is the correct answer, not a lookalike list.
            if result["path"] == "unanswerable" and intent.get("merchant"):
                fallback = _semantic(question, db, embed_fn, llm)
                if fallback["path"] != "unanswerable":
                    return fallback
            return result
        return _semantic(question, db, embed_fn, llm)
    if _classify(question) == "numeric":
        return _numeric(question, db)
    return _semantic(question, db, embed_fn, llm)

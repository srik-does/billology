"""Provider-swappable LLM access (Groq today, a frontier model later).

The LLM is a *language tool only* (Principles I & VI): it explains already-extracted
values, suggests a category from a controlled list, and translates questions into
queries. It never produces or computes a persisted numeric value. Callers must
treat every method's output as text/structure to validate — never as a source of
figures.

This is the Phase-2 skeleton: the interface is complete and the Groq calls are
wired, but prompt bodies are intentionally minimal and are fleshed out in the
relevant feature phases (T028 explain, T032 suggest_category, T035/T036 Q&A).
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any, Optional

from src.config import get_settings


class LLMService(ABC):
    @abstractmethod
    def explain(self, structured_bill: dict[str, Any]) -> dict[str, Any]:
        """Plain-language description of each charge (no new numbers)."""

    @abstractmethod
    def suggest_category(
        self, merchant: str, line_items: list[dict[str, Any]], known_categories: list[str]
    ) -> str:
        """Return a category from ``known_categories`` (or 'new category')."""

    @abstractmethod
    def classify_question(self, question: str) -> str:
        """Route a question to the 'numeric' or 'semantic' path."""

    @abstractmethod
    def question_to_query(self, question: str, schema: str) -> dict[str, Any]:
        """Translate a numeric question into a parameterized, allowlisted query."""

    @abstractmethod
    def summarize_results(
        self, question: str, retrieved_records: list[dict[str, Any]]
    ) -> str:
        """Summarize over already-retrieved real records (semantic path)."""

    @abstractmethod
    def label_lines(self, lines: list[dict[str, Any]]) -> dict[str, str]:
        """Label each extracted line's structural ROLE (item/total/tax/...).

        Structure only — the labels say which lines mean what; all figures are
        re-parsed from the original lines by deterministic code (Principle I).
        """


class GroqLLMService(LLMService):
    def __init__(self) -> None:
        settings = get_settings()
        self._model = settings.groq_model
        self._api_key = settings.groq_api_key

    @lru_cache(maxsize=1)
    def _client(self):  # type: ignore[no-untyped-def]
        from groq import Groq

        if not self._api_key:
            raise RuntimeError("GROQ_API_KEY missing. Set it in backend/.env.")
        return Groq(api_key=self._api_key)

    def _chat(self, system: str, user: str, json_mode: bool = False) -> str:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self._client().chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    # --- Language tasks (skeletons; expanded in feature phases) -----------

    def explain(self, structured_bill: dict[str, Any]) -> dict[str, Any]:
        system = (
            "You explain bills in plain language for a non-expert. You are given a "
            "merchant, a bill type, and a list of line items by position and "
            "description (no amounts are provided to you). "
            "Return JSON of the form "
            '{"bill_summary": str, "line_explanations": {"<position>": str}}. '
            "bill_summary: one or two sentences on what this bill is. "
            "line_explanations: for each line position, a short phrase saying what "
            "that item/charge is. "
            "CRITICAL: do NOT include any numbers, amounts, dates, percentages, or "
            "currency in your text — those are displayed separately from the record."
        )
        raw = self._chat(system, json.dumps(structured_bill), json_mode=True)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"bill_summary": raw, "line_explanations": {}}

    def suggest_category(
        self, merchant: str, line_items: list[dict[str, Any]], known_categories: list[str]
    ) -> str:
        system = (
            "Pick the single best category for this bill from the provided list. "
            "Reply with exactly one category name from the list, or 'new category' "
            "if none fit."
        )
        user = json.dumps(
            {"merchant": merchant, "line_items": line_items, "categories": known_categories}
        )
        answer = self._chat(system, user).strip()
        return answer if answer in known_categories else "new category"

    def classify_question(self, question: str) -> str:
        system = (
            "Classify the spending question as 'numeric' (aggregates/exact amounts) "
            "or 'semantic' (find/describe bills). Reply with one word."
        )
        answer = self._chat(system, question).strip().lower()
        return "numeric" if "numeric" in answer else "semantic"

    def question_to_query(self, question: str, schema: str) -> dict[str, Any]:
        system = (
            "Translate the question into a parameterized SQL query over ONLY the "
            "allowlisted schema. Return JSON {\"sql\": str, \"params\": object}. "
            "SELECT only; no DML/DDL; no tables outside the schema."
        )
        raw = self._chat(system, f"SCHEMA:\n{schema}\n\nQUESTION:\n{question}", json_mode=True)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"sql": "", "params": {}}

    def summarize_results(
        self, question: str, retrieved_records: list[dict[str, Any]]
    ) -> str:
        system = (
            "You answer a spending question using ONLY the provided records — real "
            "bills the system already retrieved as the closest matches, so assume "
            "they are relevant. Each record has merchant, amount, date, and category. "
            "Reason from ALL available fields, especially merchant, amount, and date. "
            "A missing/null field (e.g. category) means 'unknown' — it is NOT evidence "
            "that a record is irrelevant, so never dismiss a clearly relevant bill "
            "because its category is null. Do not invent any figure not present in the "
            "records. Only say the information is unavailable if the records are truly "
            "unrelated to the question."
        )
        user = json.dumps({"question": question, "records": retrieved_records})
        return self._chat(system, user).strip()

    def label_lines(self, lines: list[dict[str, Any]]) -> dict[str, str]:
        system = (
            "You label the structural role of each numbered OCR line from a retail "
            "bill or receipt. Roles: "
            "'merchant' (store/brand name header), "
            "'meta' (address, GSTIN/CIN/FSSAI numbers, cashier, date, column headers, "
            "invoice numbers), "
            "'item' (a purchased product or service charge), "
            "'continuation' (wrapped continuation of the previous item: barcodes, "
            "EAN/HSN codes, per-item discounts), "
            "'subtotal', "
            "'total' (the bill's grand total amount), "
            "'due' (net amount due / payable after round-off), "
            "'tax' (a tax amount line), "
            "'taxtable' (tax summary table rows), "
            "'roundoff' (round-off / rounding adjustment lines), "
            "'discount', "
            "'payment' (cash/card/UPI/tender/change rows), "
            "'junk' (separators, illegible noise, terms and conditions). "
            "The OCR text may be garbled — judge by position and context. "
            "Label EVERY line. "
            'Return JSON {"labels": {"<line index>": "<role>"}}. '
            "Do NOT compute, correct, or output any numbers or amounts."
        )
        raw = self._chat(system, json.dumps({"lines": lines}), json_mode=True)
        parsed = json.loads(raw)
        labels = parsed.get("labels", parsed)
        return {str(k): str(v) for k, v in labels.items()} if isinstance(labels, dict) else {}


@lru_cache
def get_llm_service() -> LLMService:
    """Factory — swap the implementation here to change providers."""
    return GroqLLMService()

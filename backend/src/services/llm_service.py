"""Provider-swappable LLM access: Groq (cloud) or Ollama (local inference).

Two distinct roles, with different rules (Constitution v2.0.0):

* **Transcriber** (``extract_bill_image``): a vision model reads a bill photo and
  transcribes what is printed — Principle I permits transcription but forbids the
  model computing, estimating, or filling in any value. Callers validate every
  transcribed figure in code before it exists anywhere (see extraction/vision.py).
* **Language tool** (everything else, Principles I & VI): explains already-extracted
  values, suggests a category from a controlled list, labels line ROLES, and
  translates questions into constrained query intents — never a source of figures.

Provider selection is per-request (see ``request_context``): users may run fully
local via Ollama or bring their own Groq key; the server's configured key is the
default. All prompt logic lives in ``ChatLLMService`` so providers only implement
``_chat`` and ``_chat_vision``.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from src.config import get_settings
from src.services.request_context import language, llm_overrides

# Explanations / summaries answer in the user's UI language; structured outputs
# (labels, intents, categories) stay English because code validates exact tokens.
_LANG_NAMES = {
    "hi": "Hindi (हिन्दी)",
    "te": "Telugu (తెలుగు)",
    "ta": "Tamil (தமிழ்)",
    "kn": "Kannada (ಕನ್ನಡ)",
    "ml": "Malayalam (മലയാളം)",
    "bn": "Bengali (বাংলা)",
    "mr": "Marathi (मराठी)",
    "gu": "Gujarati (ગુજરાતી)",
    "pa": "Punjabi (ਪੰਜਾਬੀ)",
    "or": "Odia (ଓଡ଼ିଆ)",
    "as": "Assamese (অসমীয়া)",
    "ur": "Urdu (اردو)",
}


def _lang_clause() -> str:
    name = _LANG_NAMES.get(language.get())
    return f" Write all explanatory text in {name}." if name else ""


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
    def derive_intent(
        self, question: str, categories: list[str], today: str
    ) -> dict[str, Any]:
        """Translate a spending question into a constrained query intent.

        Returns {path, category, month, merchant, aggregate}; every field is
        validated/allowlisted by the caller and the figure itself is always
        computed in code (Principle VI).
        """

    @abstractmethod
    def label_lines(self, lines: list[dict[str, Any]]) -> dict[str, str]:
        """Label each extracted line's structural ROLE (item/total/tax/...).

        Structure only — the labels say which lines mean what; all figures are
        re-parsed from the original lines by deterministic code (Principle I).
        """

    @abstractmethod
    def enrich_bill(self, bill_payload: dict[str, Any]) -> dict[str, Any]:
        """Generate descriptive search labels for a bill being saved.

        Returns {"tags": [str], "merchant_aliases": [str]} — labels only, used
        to widen Q&A retrieval (embedding text + keyword match). The payload is
        amount-free and the output is sanitized by the caller (Principle I).
        """

    @abstractmethod
    def extract_bill_image(self, images_b64: list[str]) -> dict[str, Any]:
        """Transcribe a photographed bill into raw lines + printed field values.

        The model acts as a transcriber under Principle I (v2): it copies what
        is printed and must never compute or invent a value. The caller
        (extraction/vision.py) treats the result as untrusted text — every
        figure is re-validated in code before entering the canonical model.
        """


class ChatLLMService(LLMService):
    """All prompt logic, provider-agnostic. Subclasses implement ``_chat``."""

    @abstractmethod
    def _chat(self, system: str, user: str, json_mode: bool = False) -> str:
        """Send one system+user exchange; return the assistant text."""

    @abstractmethod
    def _chat_vision(
        self, system: str, user: str, images_b64: list[str], json_mode: bool = False
    ) -> str:
        """Send one system+user exchange with attached JPEG images (base64)."""

    def extract_bill_image(self, images_b64: list[str]) -> dict[str, Any]:
        system = (
            "You are a high-accuracy transcriber for photos of bills, receipts, and "
            "invoices (grocery, telecom recharge, electricity, or any other; often "
            "Indian, often INR). Multiple images are pages/parts of the SAME bill. "
            "Return JSON exactly of the form "
            '{"is_bill": bool, '
            '"raw_lines": [string], '
            '"merchant": string | null, '
            '"bill_date": "YYYY-MM-DD" | null, '
            '"bill_type": "grocery" | "telecom_recharge" | "other", '
            '"currency": string | null, '
            '"uncertain_fields": [string], '
            '"subtotal": string | null, '
            '"taxable_value": string | null, '
            '"tax_rate": string | null, '
            '"tax_amount": string | null, '
            '"tax_components": [{"name": string, "rate": string | null, "amount": string}], '
            '"total_amount": string | null, '
            '"line_items": [{"description": string, "quantity": string | null, '
            '"unit_amount": string | null, "line_total": string | null}]}. '
            "TRANSCRIPTION RULES (absolute): copy every value digit-for-digit exactly "
            "as printed. NEVER compute, sum, estimate, round, or fill in a value that "
            "is not printed — if a field is not printed or is unreadable, use null. "
            "raw_lines: every visible printed line of text, top to bottom, transcribed "
            "verbatim. Amounts as plain digit strings without currency symbols or "
            "thousands separators (e.g. '1234.56'). "
            "uncertain_fields: the names of exactly those fields whose printed value "
            "you could NOT read with certainty (blurry, faded, crumpled, cut off), "
            "chosen from: 'merchant', 'bill_date', 'subtotal', 'taxable_value', 'tax', "
            "'total_amount', 'line_items'. Empty list when everything is legible. Do "
            "NOT list fields you read clearly. Listing a field never excuses guessing "
            "— still transcribe your best reading of it, or null. "
            "total_amount: the grand total / net amount payable as printed — never a "
            "GST-summary or taxable-value figure. "
            "taxable_value: the printed total taxable value/amount (often in a GST "
            "summary table), when printed. "
            "tax_amount: only a single printed total-tax figure; when tax is printed "
            "split into components (CGST/SGST/IGST), put each printed component row in "
            "tax_components instead and leave tax_amount null. tax_rate: printed "
            "percentage digits only (e.g. '18'). "
            "line_items: purchased products / service charges only — exclude totals, "
            "subtotals, tax rows, discounts, and payment/tender/change rows. "
            "line_total is the amount PRINTED on that row; when a row shows a quantity "
            "but only ONE amount, that printed amount is the line_total — NEVER multiply "
            "quantity by a price to produce it. Fill unit_amount only when the row "
            "prints both a per-unit price and a row total. "
            "is_bill: false when the image is not a bill, receipt, or invoice."
        )
        raw = self._chat_vision(
            system, "Transcribe this bill.", images_b64, json_mode=True
        )
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}

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
            + _lang_clause()
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
            "they are relevant. Each record has merchant, total amount, date, "
            "category, and MAY include line_items (each an item with its amount). "
            "Reason from ALL available fields. When the user asks what is in a bill "
            "or to break it down, list that bill's line_items with their amounts; if "
            "a record has no line_items, say only the total is available for that "
            "bill. A missing/null field (e.g. category) means 'unknown' — it is NOT "
            "evidence that a record is irrelevant, so never dismiss a clearly "
            "relevant bill because its category is null. Do not invent any figure "
            "not present in the records. Only say the information is unavailable if "
            "the records are truly unrelated to the question."
            + _lang_clause()
        )
        user = json.dumps({"question": question, "records": retrieved_records})
        return self._chat(system, user).strip()

    def derive_intent(
        self, question: str, categories: list[str], today: str
    ) -> dict[str, Any]:
        system = (
            "You translate a question about personal spending into a constrained "
            "query intent over a bills database. The question may be in English "
            "or any Indian language. Return JSON exactly of the form "
            '{"path": "numeric" | "semantic", "category": string | null, '
            '"month": "YYYY-MM" | null, "merchant": string | null, '
            '"aggregate": "sum" | "count" | "latest" | "average"}. '
            "'numeric' = the user asks for an amount, count, average, or most "
            "recent figure. 'semantic' = the user wants to find, list, or "
            "describe bills. "
            "category MUST be exactly one of the provided category names, or null "
            "if none clearly applies. merchant only when a specific store/vendor "
            "is named. Resolve relative times ('last month', 'this month') using "
            "the provided current date. Do NOT compute or output any amounts."
        )
        user = json.dumps({"question": question, "categories": categories, "today": today})
        raw = self._chat(system, user, json_mode=True)
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}

    def enrich_bill(self, bill_payload: dict[str, Any]) -> dict[str, Any]:
        system = (
            "You generate search labels for a saved bill so the user can find it "
            "later with natural questions. You are given merchant, bill type, "
            "category, and item descriptions (no amounts). Return JSON "
            '{"tags": [string], "merchant_aliases": [string]}. '
            "tags: 5-15 short lowercase keywords/phrases a person might use when "
            "asking about this bill — item kinds, shopping purpose, colloquial and "
            "regional words (e.g. 'kirana' for a grocery store), common synonyms. "
            "merchant_aliases: common alternate spellings, spacings, and short "
            "forms of the merchant name (e.g. 'D-Mart', 'd mart', 'Avenue "
            "Supermarts' for 'DMart'). "
            "Do NOT output any amounts, dates, or numbers that look like figures."
        )
        raw = self._chat(system, json.dumps(bill_payload), json_mode=True)
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}

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


class GroqLLMService(ChatLLMService):
    def __init__(self, api_key: str, model: str, vision_model: str = "") -> None:
        self._model = model
        self._vision_model = vision_model
        self._api_key = api_key
        self._client_instance = None

    def _client(self):  # type: ignore[no-untyped-def]
        from groq import Groq

        if not self._api_key:
            raise RuntimeError("GROQ_API_KEY missing. Set it in backend/.env.")
        if self._client_instance is None:
            self._client_instance = Groq(api_key=self._api_key)
        return self._client_instance

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

    def _chat_vision(
        self, system: str, user: str, images_b64: list[str], json_mode: bool = False
    ) -> str:
        if not self._vision_model:
            raise RuntimeError("No Groq vision model configured (GROQ_VISION_MODEL).")
        content: list[dict[str, Any]] = [{"type": "text", "text": user}]
        content += [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
            for b64 in images_b64
        ]
        kwargs: dict[str, Any] = {
            "model": self._vision_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            "temperature": 0,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self._client().chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""


class OllamaLLMService(ChatLLMService):
    """Local inference via an Ollama server — no data leaves the machine."""

    def __init__(self, base_url: str, model: str, vision_model: str = "") -> None:
        self._url = base_url.rstrip("/")
        self._model = model
        self._vision_model = vision_model

    def _chat(self, system: str, user: str, json_mode: bool = False) -> str:
        import httpx  # bundled transitively (supabase/fastapi stack)

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0},
        }
        if json_mode:
            payload["format"] = "json"
        resp = httpx.post(f"{self._url}/api/chat", json=payload, timeout=120.0)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")

    def _chat_vision(
        self, system: str, user: str, images_b64: list[str], json_mode: bool = False
    ) -> str:
        import httpx

        if not self._vision_model:
            raise RuntimeError("No Ollama vision model configured (OLLAMA_VISION_MODEL).")
        payload: dict[str, Any] = {
            "model": self._vision_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user, "images": images_b64},
            ],
            "stream": False,
            "options": {"temperature": 0},
        }
        if json_mode:
            payload["format"] = "json"
        # Vision inference on local hardware is slow — allow a longer budget.
        resp = httpx.post(f"{self._url}/api/chat", json=payload, timeout=300.0)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")


# Small instance cache so per-request construction stays cheap.
_INSTANCES: dict[tuple, LLMService] = {}


def get_llm_service() -> LLMService:
    """Build the provider chosen for this request (default: server-configured).

    Order of precedence: per-request header overrides (request_context) →
    server settings. Users can pick local Ollama or bring their own Groq key.
    """
    settings = get_settings()
    over = llm_overrides.get()
    provider = (over.get("provider") or settings.llm_provider or "groq").lower()

    if provider == "ollama":
        url = over.get("ollama_url") or settings.ollama_url
        model = over.get("ollama_model") or settings.ollama_model
        vision = settings.ollama_vision_model
        key = ("ollama", url, model, vision)
        if key not in _INSTANCES:
            _INSTANCES[key] = OllamaLLMService(url, model, vision)
    else:
        api_key = over.get("groq_key") or settings.groq_api_key
        model = settings.groq_model
        vision = settings.groq_vision_model
        key = ("groq", api_key, model, vision)
        if key not in _INSTANCES:
            _INSTANCES[key] = GroqLLMService(api_key, model, vision)

    if len(_INSTANCES) > 32:  # bound the cache (many BYO keys)
        _INSTANCES.clear()
        _INSTANCES[key] = (
            OllamaLLMService(*key[1:]) if key[0] == "ollama" else GroqLLMService(*key[1:])
        )
    return _INSTANCES[key]

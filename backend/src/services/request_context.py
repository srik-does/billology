"""Per-request context: LLM provider overrides and UI language.

Set by middleware in ``main.py`` from request headers, read by ``llm_service``
and ``qa_service``. Lets a user choose local inference (Ollama) or bring their
own Groq key, and receive explanations in their language — without the clients
ever talking to a provider directly (Principle IV stays intact).
"""

from __future__ import annotations

from contextvars import ContextVar

# {"provider": "groq"|"ollama", "groq_key": str, "ollama_url": str, "ollama_model": str}
llm_overrides: ContextVar[dict] = ContextVar("llm_overrides", default={})

# "en" | "hi" | "te"
language: ContextVar[str] = ContextVar("language", default="en")

SUPPORTED_LANGUAGES = ("en", "hi", "te")

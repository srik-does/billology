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

# One of SUPPORTED_LANGUAGES below (ISO 639-1).
language: ContextVar[str] = ContextVar("language", default="en")

# The caller's raw Supabase access token (JWT), set by middleware from the
# Authorization header. persistence reads it to talk to the database AS the
# user, so Postgres RLS enforces per-user data isolation. Empty = no
# authenticated user (admin/service path or an unauthenticated request).
auth_token: ContextVar[str] = ContextVar("auth_token", default="")

# The authenticated user's id (JWT `sub`), set once the token is verified.
user_id: ContextVar[str] = ContextVar("user_id", default="")

# English + 12 Indian languages. Keep in sync with the mobile Language type,
# the web language <select>, qa_service._TEMPLATES, and llm_service._LANG_NAMES
# (test_i18n.py enforces the backend side).
SUPPORTED_LANGUAGES = (
    "en", "hi", "te", "ta", "kn", "ml", "bn", "mr", "gu", "pa", "or", "as", "ur"
)

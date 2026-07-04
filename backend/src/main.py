"""FastAPI application entry point — the single trust boundary.

Wires the feature routers (bills, categories, dashboard, qa), the bundled web
client, the health check, and a uniform error handler. All client traffic —
mobile app, web demo, or API consumers — passes through this service; clients
never talk to the LLM provider or the database directly.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from src.config import get_settings

app = FastAPI(
    title="Billology Backend API",
    version="2.0.4",
    description=(
        "AI-powered bill ingestion and analysis. The AI reads and explains, "
        "but never invents a number: every figure is extracted from the bill "
        "and re-validated in code."
    ),
)

# Browser origins allowed to call the API (ALLOWED_ORIGINS, comma-separated).
# Defaults to "*" so the bundled web demo works from any host; set explicit
# origins in production.
_origins = [o.strip() for o in get_settings().allowed_origins.split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """Per-request LLM provider override + UI language (see request_context).

    Headers: X-LLM-Provider (groq|ollama), X-Groq-Key (bring-your-own-token),
    X-Ollama-Url, X-Ollama-Model, X-Language (one of
    request_context.SUPPORTED_LANGUAGES). The clients still only ever talk to
    this backend — never to a provider directly.
    """
    from src.services.request_context import (
        SUPPORTED_LANGUAGES,
        auth_token,
        language,
        llm_overrides,
    )

    # Forward the caller's Supabase access token to the DB layer so every query
    # runs under Postgres RLS as that user (per-user isolation). We only carry
    # the raw token here; signature verification + 401s happen in the
    # require_user route dependency (services/auth.py).
    bearer = (request.headers.get("authorization") or "").strip()
    token_value = bearer[7:].strip() if bearer[:7].lower() == "bearer " else ""
    token_auth = auth_token.set(token_value)

    overrides: dict = {}
    provider = (request.headers.get("x-llm-provider") or "").strip().lower()
    if provider in ("groq", "ollama"):
        overrides["provider"] = provider
    groq_key = (request.headers.get("x-groq-key") or "").strip()
    if groq_key:
        overrides["groq_key"] = groq_key
    ollama_url = (request.headers.get("x-ollama-url") or "").strip()
    if ollama_url.startswith(("http://", "https://")):
        overrides["ollama_url"] = ollama_url
    ollama_model = (request.headers.get("x-ollama-model") or "").strip()
    if ollama_model:
        overrides["ollama_model"] = ollama_model

    lang = (request.headers.get("x-language") or "en").strip().lower()
    if lang not in SUPPORTED_LANGUAGES:
        lang = "en"

    token_overrides = llm_overrides.set(overrides)
    token_language = language.set(lang)
    try:
        return await call_next(request)
    finally:
        llm_overrides.reset(token_overrides)
        language.reset(token_language)
        auth_token.reset(token_auth)


_WEB_INDEX = Path(__file__).parent / "web" / "index.html"


@app.get("/", include_in_schema=False)
def home():
    """Serve the single-page bill-analyzer demo client."""
    return FileResponse(_WEB_INDEX)


@app.get("/config", include_in_schema=False)
def web_config() -> dict[str, str]:
    """Public bootstrap config for the browser client.

    The web app is a static file, so it can't read env directly; it fetches the
    Supabase project URL + anon key here to start the Google sign-in handshake.
    Both values are publishable (the anon key is designed to ship to browsers);
    no secret (service key / JWT secret) is ever exposed.
    """
    from src.config import get_settings

    settings = get_settings()
    return {
        "supabaseUrl": settings.supabase_url,
        "supabaseAnonKey": settings.supabase_anon_key,
    }


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log the full traceback server-side so root causes are never swallowed.
    # Clients get a generic message: internal exception details (paths, SQL,
    # provider errors) must not leak across the trust boundary. Set
    # DEBUG_ERRORS=true locally to include them while debugging.
    logging.getLogger("billology").exception(
        "Unhandled error on %s %s", request.method, request.url.path
    )
    detail = (
        f"{type(exc).__name__}: {exc}"
        if get_settings().debug_errors
        else "Something went wrong on our side. Please try again."
    )
    return JSONResponse(status_code=500, content={"error": "internal_error", "detail": detail})


def _include_routers() -> None:
    """Include the feature routers; a router that fails to import is a bug we log loudly."""
    # Category endpoints live inside the bills router; there is no separate module.
    for module_name in ("bills", "dashboard", "qa"):
        try:
            module = __import__(f"src.api.{module_name}", fromlist=["router"])
            app.include_router(module.router)
        except ImportError as exc:
            logging.getLogger("billology").error(
                "Router 'src.api.%s' failed to load and is NOT mounted: %s", module_name, exc
            )


_include_routers()

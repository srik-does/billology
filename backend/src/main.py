"""FastAPI application entry point — the single trust boundary.

Feature routers (bills, categories, dashboard, qa) are wired here as they are
implemented in Phases 3+. This Phase-2 skeleton provides the app, a health
check, and a uniform error handler; routers are included defensively so the app
boots even before every router module exists.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(title="Billology Backend API", version="0.1.0")

# Permissive CORS so the bundled web demo (or a separately hosted client) can
# call the API during the demo. Tighten for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    from src.services.request_context import SUPPORTED_LANGUAGES, language, llm_overrides

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


_WEB_INDEX = Path(__file__).parent / "web" / "index.html"


@app.get("/", include_in_schema=False)
def home():
    """Serve the single-page bill-analyzer demo client."""
    return FileResponse(_WEB_INDEX)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log the full traceback server-side so root causes are never swallowed,
    # and return the error type/message to aid debugging during the demo.
    logging.getLogger("billology").exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": f"{type(exc).__name__}: {exc}"},
    )


def _include_routers() -> None:
    """Include feature routers if their modules are present (added in later phases)."""
    try:
        from src.api import bills  # noqa: WPS433

        app.include_router(bills.router)
    except ImportError:
        pass
    for module_name in ("categories", "dashboard", "qa"):
        try:
            module = __import__(f"src.api.{module_name}", fromlist=["router"])
            app.include_router(module.router)
        except ImportError:
            pass


_include_routers()

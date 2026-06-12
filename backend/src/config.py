"""Centralized configuration loaded from environment / .env.

All provider keys and the embedding contract live here so that no other module
hard-codes them. The embedding dimension is pinned and asserted against the
model at startup (see embedding_service) to prevent the pgvector mismatch
called out in research.md.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor to backend/.env so scripts work from any working directory
# (the server is launched from backend/, but scripts run from the repo root).
_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    # Supabase
    supabase_url: str = ""
    # Accept either SUPABASE_KEY or SUPABASE_SERVICE_KEY (the service-role key).
    supabase_key: str = Field(
        default="",
        validation_alias=AliasChoices("SUPABASE_KEY", "SUPABASE_SERVICE_KEY"),
    )
    supabase_bucket: str = "bills"

    # LLM provider: "groq" (cloud) or "ollama" (local inference). Per-request
    # header overrides let users switch or bring their own key (request_context).
    llm_provider: str = "groq"

    # Groq (provider-swappable LLM)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Ollama (local inference)
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # Vision extraction (v2): bill images are transcribed by a multimodal LLM
    # instead of local OCR (Constitution v2.0.0, Principles I & IV). Set
    # VISION_EXTRACTION=false to force the deterministic OCR pipeline, which
    # also remains the automatic fallback when the vision call fails.
    vision_extraction: bool = True
    groq_vision_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    ollama_vision_model: str = "llama3.2-vision"

    # Embeddings (fastembed, local). Dimension MUST match the pgvector column.
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384


@lru_cache
def get_settings() -> Settings:
    return Settings()

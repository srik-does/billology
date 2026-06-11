"""Centralized configuration loaded from environment / .env.

All provider keys and the embedding contract live here so that no other module
hard-codes them. The embedding dimension is pinned and asserted against the
model at startup (see embedding_service) to prevent the pgvector mismatch
called out in research.md.
"""

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Supabase
    supabase_url: str = ""
    # Accept either SUPABASE_KEY or SUPABASE_SERVICE_KEY (the service-role key).
    supabase_key: str = Field(
        default="",
        validation_alias=AliasChoices("SUPABASE_KEY", "SUPABASE_SERVICE_KEY"),
    )
    supabase_bucket: str = "bills"

    # Groq (provider-swappable LLM)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Embeddings (fastembed, local). Dimension MUST match the pgvector column.
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384


@lru_cache
def get_settings() -> Settings:
    return Settings()

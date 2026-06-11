"""Supabase persistence: Postgres rows + private Storage for original artifacts.

This module is the only place that talks to the database/storage. The mobile
client never reaches Supabase directly (Principle IV — single trust boundary).
"""

from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Any, Optional

from src.config import get_settings


class PersistenceError(RuntimeError):
    """Raised when a database write fails or returns no row (never swallowed)."""


@lru_cache
def get_client():
    """Return a cached Supabase client built from service credentials."""
    from supabase import create_client

    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_key:
        raise RuntimeError(
            "Supabase credentials missing. Set SUPABASE_URL and SUPABASE_KEY "
            "(or SUPABASE_SERVICE_KEY) in backend/.env."
        )
    return create_client(settings.supabase_url, settings.supabase_key)


# --- Storage --------------------------------------------------------------

def upload_artifact(file_bytes: bytes, filename: str, content_type: str) -> str:
    """Upload an original bill artifact to the private bucket; return its path.

    The bucket is private; readers must mint a signed URL (see ``signed_url``).
    """
    settings = get_settings()
    path = f"{uuid.uuid4()}/{filename}"
    get_client().storage.from_(settings.supabase_bucket).upload(
        path, file_bytes, {"content-type": content_type, "upsert": "false"}
    )
    return path


def signed_url(path: str, expires_in: int = 3600) -> str:
    settings = get_settings()
    resp = get_client().storage.from_(settings.supabase_bucket).create_signed_url(
        path, expires_in
    )
    return resp.get("signedURL") or resp.get("signed_url", "")


# --- Tables ---------------------------------------------------------------

def insert_row(table: str, row: dict[str, Any]) -> dict[str, Any]:
    """Insert one row and return it. Raises PersistenceError on failure.

    Requests representation so the inserted row (with its generated id) is
    returned; an empty response usually means RLS blocked the write or a
    non-service key was used. We never treat that as success.
    """
    try:
        # supabase-py returns the inserted representation by default.
        resp = get_client().table(table).insert(row).execute()
    except Exception as exc:  # postgrest APIError, network, etc.
        raise PersistenceError(f"Insert into '{table}' failed: {exc}") from exc

    data = getattr(resp, "data", None)
    if not data:
        raise PersistenceError(
            f"Insert into '{table}' returned no row. Likely causes: RLS is enabled "
            f"and the key is not the service-role key, or the row violates a "
            f"constraint. Verify SUPABASE_KEY is the service key."
        )
    return data[0]


def select(table: str, filters: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    query = get_client().table(table).select("*")
    for key, value in (filters or {}).items():
        query = query.eq(key, value)
    return query.execute().data or []


def delete_rows(table: str, filters: dict[str, Any]) -> int:
    """Delete rows matching the filters; return the number deleted."""
    if not filters:
        raise PersistenceError("delete_rows requires at least one filter.")
    try:
        query = get_client().table(table).delete()
        for key, value in filters.items():
            query = query.eq(key, value)
        resp = query.execute()
    except Exception as exc:
        raise PersistenceError(f"Delete from '{table}' failed: {exc}") from exc
    return len(resp.data or [])


def delete_all(table: str) -> int:
    """Delete every row in a table (children cascade); return the count."""
    try:
        # PostgREST requires a filter on DELETE; match every real uuid.
        resp = (
            get_client()
            .table(table)
            .delete()
            .neq("id", "00000000-0000-0000-0000-000000000000")
            .execute()
        )
    except Exception as exc:
        raise PersistenceError(f"Delete-all from '{table}' failed: {exc}") from exc
    return len(resp.data or [])


def match_bills(embedding_literal: str, match_count: int = 5) -> list[dict[str, Any]]:
    """Semantic search via the match_bills RPC (pgvector cosine). Returns rows."""
    try:
        resp = get_client().rpc(
            "match_bills",
            {"query_embedding": embedding_literal, "match_count": match_count},
        ).execute()
    except Exception as exc:
        raise PersistenceError(f"match_bills RPC failed: {exc}") from exc
    return resp.data or []

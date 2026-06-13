"""Supabase persistence: Postgres rows + private Storage for original artifacts.

This module is the only place that talks to the database/storage. The mobile
client never reaches Supabase directly (Principle IV — single trust boundary).
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from src.config import get_settings
from src.services.request_context import auth_token


class PersistenceError(RuntimeError):
    """Raised when a database write fails or returns no row (never swallowed)."""


_service_client = None
# Bounded cache of per-user clients, keyed by access token. Tokens rotate on
# refresh, so stale entries are simply superseded and eventually evicted.
_user_clients: dict[str, Any] = {}


def _service() -> Any:
    """The service-role client — bypasses RLS. For admin/seed/no-auth paths."""
    global _service_client
    if _service_client is None:
        from supabase import create_client

        settings = get_settings()
        if not settings.supabase_url or not settings.supabase_key:
            raise RuntimeError(
                "Supabase credentials missing. Set SUPABASE_URL and SUPABASE_KEY "
                "(or SUPABASE_SERVICE_KEY) in backend/.env."
            )
        _service_client = create_client(settings.supabase_url, settings.supabase_key)
    return _service_client


def _user_client(token: str) -> Any:
    """A client that talks to the DB AS the caller, so RLS isolates their data.

    Built with the anon key + the user's access token as the Authorization
    bearer; PostgREST then resolves ``auth.uid()`` from the token and RLS
    policies scope every row to that user.
    """
    client = _user_clients.get(token)
    if client is not None:
        return client
    from supabase import create_client

    try:
        from supabase.lib.client_options import ClientOptions
    except Exception:  # pragma: no cover - import path varies by version
        from supabase import ClientOptions  # type: ignore

    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_ANON_KEY are required for user-scoped "
            "(RLS) database access. Set them in backend/.env."
        )
    options = ClientOptions(headers={"Authorization": f"Bearer {token}"})
    client = create_client(settings.supabase_url, settings.supabase_anon_key, options)
    if len(_user_clients) > 64:  # bound the cache (many concurrent users)
        _user_clients.clear()
    _user_clients[token] = client
    return client


def get_client():
    """Return the Supabase client for the current request.

    When the caller is authenticated (a token is on the request context), the
    client runs under their identity so Postgres RLS enforces per-user data
    isolation. With no token it falls back to the service-role client, used by
    admin scripts, seeding, and any unauthenticated internal path.
    """
    token = auth_token.get()
    return _user_client(token) if token else _service()


# --- Storage --------------------------------------------------------------

def upload_artifact(file_bytes: bytes, filename: str, content_type: str) -> str:
    """Upload an original bill artifact to the private bucket; return its path.

    Storage uses the service client (bypasses storage RLS). Per-user isolation
    still holds: a file's path is only reachable through its bill row, which is
    RLS-scoped to the owner, and signed URLs are minted server-side only for
    bills the caller can read.
    """
    settings = get_settings()
    path = f"{uuid.uuid4()}/{filename}"
    _service().storage.from_(settings.supabase_bucket).upload(
        path, file_bytes, {"content-type": content_type, "upsert": "false"}
    )
    return path


def signed_url(path: str, expires_in: int = 3600) -> str:
    settings = get_settings()
    resp = _service().storage.from_(settings.supabase_bucket).create_signed_url(
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


def update_rows(table: str, filters: dict[str, Any], values: dict[str, Any]) -> int:
    """Update rows matching the filters; return the number updated."""
    if not filters:
        raise PersistenceError("update_rows requires at least one filter.")
    try:
        query = get_client().table(table).update(values)
        for key, value in filters.items():
            query = query.eq(key, value)
        resp = query.execute()
    except Exception as exc:
        raise PersistenceError(f"Update of '{table}' failed: {exc}") from exc
    return len(resp.data or [])


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

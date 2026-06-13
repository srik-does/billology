"""Authentication at the trust boundary.

The mobile client signs in with Google via Supabase Auth and sends the
resulting Supabase access token (a JWT) as ``Authorization: Bearer <token>``.
Here we verify that token's signature with the project's JWT secret (HS256),
authenticating the user. The verified token is also forwarded to the database
layer (see persistence) so every query runs under Postgres RLS as that user —
data isolation is enforced by the database, not just trusted in app code.

``require_user`` is the FastAPI dependency that guards user-facing routes:
no valid token → HTTP 401, before any handler runs.
"""

from __future__ import annotations

import logging
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config import get_settings

logger = logging.getLogger("billology.auth")

# Supabase mints access tokens with this audience for signed-in users.
_AUDIENCE = "authenticated"

_bearer = HTTPBearer(auto_error=False)


class AuthError(HTTPException):
    def __init__(self, detail: str = "Not authenticated") -> None:
        super().__init__(status_code=401, detail=detail)


def verify_token(token: str) -> dict:
    """Verify a Supabase access token and return its claims.

    Raises ``AuthError`` (HTTP 401) on any invalid/expired/forged token.
    """
    secret = get_settings().supabase_jwt_secret
    if not secret:
        # Misconfiguration must fail closed, never silently accept everyone.
        logger.error("SUPABASE_JWT_SECRET is not set; cannot authenticate requests.")
        raise AuthError("Auth not configured")
    try:
        return jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=_AUDIENCE,
        )
    except jwt.PyJWTError as exc:
        raise AuthError(f"Invalid token: {exc}") from exc


def require_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> str:
    """FastAPI dependency: authenticate the caller, return their user id.

    The raw token is stashed on ``request.state`` so the middleware-set
    ``auth_token`` context var (used by persistence for RLS) is guaranteed to
    match the verified caller even if header casing differed.
    """
    if credentials is None or not credentials.credentials:
        raise AuthError()
    claims = verify_token(credentials.credentials)
    uid = claims.get("sub")
    if not uid:
        raise AuthError("Token missing subject")
    request.state.user_id = uid
    return uid

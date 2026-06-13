"""Authentication at the trust boundary.

The mobile client signs in with Google via Supabase Auth and sends the
resulting Supabase access token (a JWT) as ``Authorization: Bearer <token>``.
Here we verify that token's signature, authenticating the user. The verified
token is also forwarded to the database layer (see persistence) so every query
runs under Postgres RLS as that user — data isolation is enforced by the
database, not just trusted in app code.

Supabase signs access tokens one of two ways depending on the project:
asymmetric **ES256/RS256** signing keys (current default — verified against the
project's published JWKS) or a legacy shared **HS256** secret. We support both,
choosing by the token's own ``alg`` header.

``require_user`` is the FastAPI dependency that guards user-facing routes:
no valid token → HTTP 401, before any handler runs.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from src.config import get_settings

logger = logging.getLogger("billology.auth")

# Supabase mints access tokens with this audience for signed-in users.
_AUDIENCE = "authenticated"

# Asymmetric algorithms we accept (verified via JWKS public keys). HS256 is
# handled separately with the shared secret; nothing else is allowed (so a
# forged ``alg: none`` or an algorithm-confusion attempt is rejected).
_ASYMMETRIC = {"ES256", "ES384", "ES512", "RS256", "RS384", "RS512"}

_bearer = HTTPBearer(auto_error=False)


class AuthError(HTTPException):
    def __init__(self, detail: str = "Not authenticated") -> None:
        super().__init__(status_code=401, detail=detail)


@lru_cache(maxsize=4)
def _jwk_client(jwks_url: str, apikey: str) -> PyJWKClient:
    """Cached JWKS client (caches the fetched keys, refreshes on unknown kid)."""
    headers = {"apikey": apikey} if apikey else None
    return PyJWKClient(jwks_url, headers=headers)


def verify_token(token: str) -> dict:
    """Verify a Supabase access token and return its claims.

    Raises ``AuthError`` (HTTP 401) on any invalid/expired/forged token.
    """
    settings = get_settings()
    try:
        alg = jwt.get_unverified_header(token).get("alg", "")
    except jwt.PyJWTError as exc:
        raise AuthError(f"Invalid token: {exc}") from exc

    try:
        if alg == "HS256":
            secret = settings.supabase_jwt_secret
            if not secret:
                # Misconfiguration must fail closed, never accept everyone.
                logger.error("SUPABASE_JWT_SECRET is not set; cannot verify HS256 tokens.")
                raise AuthError("Auth not configured")
            return jwt.decode(token, secret, algorithms=["HS256"], audience=_AUDIENCE)

        if alg in _ASYMMETRIC:
            if not settings.supabase_url:
                logger.error("SUPABASE_URL is not set; cannot fetch JWKS.")
                raise AuthError("Auth not configured")
            jwks_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
            signing_key = _jwk_client(jwks_url, settings.supabase_anon_key).get_signing_key_from_jwt(token)
            return jwt.decode(token, signing_key.key, algorithms=[alg], audience=_AUDIENCE)

        raise AuthError(f"Unsupported token algorithm: {alg or 'none'}")
    except AuthError:
        raise
    except jwt.PyJWTError as exc:
        raise AuthError(f"Invalid token: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - JWKS fetch / network: fail closed
        logger.error("Token verification failed: %s", exc)
        raise AuthError("Token verification failed") from exc


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

"""Boundary authentication + route guarding.

The mobile client authenticates with a Supabase access token; the backend
verifies its signature (ES256 via JWKS, or legacy HS256) and rejects anything
invalid. User-facing routes are guarded so an unauthenticated request never
reaches the data layer.
"""

from __future__ import annotations

from types import SimpleNamespace

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient
from src.config import get_settings
from src.services import auth, persistence
from src.services.auth import AuthError, verify_token


def _token(secret: str, sub: str = "user-123", aud: str = "authenticated", **extra) -> str:
    return pyjwt.encode({"sub": sub, "aud": aud, **extra}, secret, algorithm="HS256")


def test_verify_token_roundtrip(monkeypatch):
    monkeypatch.setattr(get_settings(), "supabase_jwt_secret", "unit-test-secret-32-bytes-minimum!!")
    claims = verify_token(_token("unit-test-secret-32-bytes-minimum!!"))
    assert claims["sub"] == "user-123"


def test_verify_token_rejects_bad_signature(monkeypatch):
    monkeypatch.setattr(get_settings(), "supabase_jwt_secret", "unit-test-secret-32-bytes-minimum!!")
    with pytest.raises(AuthError):
        verify_token(_token("another-wrong-secret-32-bytes-minimum"))


def test_verify_token_rejects_wrong_audience(monkeypatch):
    monkeypatch.setattr(get_settings(), "supabase_jwt_secret", "unit-test-secret-32-bytes-minimum!!")
    with pytest.raises(AuthError):
        verify_token(_token("unit-test-secret-32-bytes-minimum!!", aud="anon"))


def test_verify_token_unconfigured_fails_closed(monkeypatch):
    # A missing secret must reject everyone, never accept all.
    monkeypatch.setattr(get_settings(), "supabase_jwt_secret", "")
    with pytest.raises(AuthError):
        verify_token(_token("anything"))


def test_verify_token_accepts_es256_via_jwks(monkeypatch):
    # Current Supabase projects sign access tokens with asymmetric ES256 keys,
    # verified against the project JWKS rather than the legacy HS256 secret.
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = ec.generate_private_key(ec.SECP256R1())
    token = pyjwt.encode(
        {"sub": "user-es256", "aud": "authenticated"},
        private_key,
        algorithm="ES256",
    )
    monkeypatch.setattr(get_settings(), "supabase_url", "https://proj.supabase.co")
    # Stand in for the JWKS fetch: hand back the matching public key.
    monkeypatch.setattr(
        auth,
        "_jwk_client",
        lambda *a, **k: SimpleNamespace(
            get_signing_key_from_jwt=lambda _t: SimpleNamespace(key=private_key.public_key())
        ),
    )
    claims = verify_token(token)
    assert claims["sub"] == "user-es256"


def test_verify_token_rejects_unsupported_alg():
    # alg:none (and anything outside HS256/ES*/RS*) must be refused.
    token = pyjwt.encode({"sub": "x", "aud": "authenticated"}, key=None, algorithm="none")
    with pytest.raises(AuthError):
        verify_token(token)


def test_guarded_route_rejects_unauthenticated():
    from src.main import app

    resp = TestClient(app).get("/bills")
    assert resp.status_code == 401


def test_guarded_route_accepts_valid_token(monkeypatch):
    from src.main import app

    monkeypatch.setattr(get_settings(), "supabase_jwt_secret", "unit-test-secret-32-bytes-minimum!!")
    # Don't touch the real database — prove only that auth lets the call through.
    monkeypatch.setattr(persistence, "select", lambda *a, **k: [])

    resp = TestClient(app).get("/bills", headers={"Authorization": f"Bearer {_token('unit-test-secret-32-bytes-minimum!!')}"})
    assert resp.status_code == 200
    assert resp.json() == []

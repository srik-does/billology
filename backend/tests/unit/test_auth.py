"""Boundary authentication + route guarding.

The mobile client authenticates with a Supabase access token; the backend
verifies its signature (HS256) and rejects anything invalid. User-facing routes
are guarded so an unauthenticated request never reaches the data layer.
"""

from __future__ import annotations

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient
from src.config import get_settings
from src.services import persistence
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

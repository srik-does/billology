"""Integration tests: real HTTP requests through the full app stack.

These exercise the actual wiring — middleware (guardrails, request context),
auth dependency, routers, and the deterministic extraction pipeline — via
FastAPI's TestClient, not individual services in isolation. They run fully
offline: LLM keys and Supabase config are blanked so every code path takes its
deterministic fallback (pasted-text extraction is deterministic by design).
"""

from __future__ import annotations

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient
from src.config import get_settings
from src.main import app
from src.services import persistence, rate_limit

_SECRET = "integration-test-secret-32-bytes-long!!"


def _token(sub: str = "itest-user") -> str:
    return pyjwt.encode({"sub": sub, "aud": "authenticated"}, _SECRET, algorithm="HS256")


def _auth(sub: str = "itest-user") -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(sub)}"}


# A well-formed bill the deterministic text parser extracts completely.
BILL_TEXT = """QuickMart
Rice 500.00
Oil 200.00
Sub Total 700.00
C.G.S.T. 9% 63.00
S.G.S.T. 9% 63.00
Grand Total 826.00
"""

# Same bill with a provably wrong grand total (700 + 126 tax != 900).
BROKEN_BILL_TEXT = """QuickMart
Rice 500.00
Oil 200.00
Sub Total 700.00
C.G.S.T. 9% 63.00
S.G.S.T. 9% 63.00
Grand Total 900.00
"""


@pytest.fixture(autouse=True)
def offline_settings(monkeypatch):
    """Force every external dependency into its deterministic fallback."""
    settings = get_settings()
    monkeypatch.setattr(settings, "supabase_jwt_secret", _SECRET)
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_key", "")
    monkeypatch.setattr(settings, "groq_api_key", "")
    monkeypatch.setattr(settings, "vision_extraction", False)
    # Fresh limiter counters per test so tests can't throttle each other.
    rate_limit.reset_limiters()
    yield
    rate_limit.reset_limiters()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# --- auth boundary -----------------------------------------------------------


def test_health_is_public(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/bills"),
        ("post", "/bills:process"),
        ("post", "/qa"),
        ("get", "/dashboard/by-category"),
        ("get", "/dashboard/monthly"),
    ],
)
def test_user_routes_reject_unauthenticated(client, method, path):
    resp = getattr(client, method)(path)
    assert resp.status_code == 401


def test_user_routes_reject_forged_token(client):
    forged = pyjwt.encode(
        {"sub": "attacker", "aud": "authenticated"},
        "wrong-secret-that-is-32-bytes-long!!!!",
        algorithm="HS256",
    )
    resp = client.get("/bills", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401


# --- extract → verify → explain over HTTP -------------------------------------


def test_process_pasted_bill_end_to_end(client):
    resp = client.post("/bills:process", data={"text": BILL_TEXT}, headers=_auth())
    assert resp.status_code == 200
    bill = resp.json()

    # Figures come from the bill text, traced and exact.
    assert bill["total_amount"]["value"] == "826.00"
    assert {li["description"]["value"] for li in bill["line_items"]} >= {"Rice", "Oil"}
    assert bill["tax_amount"]["value"] == "126.00"
    # A correct bill must not be flagged.
    assert bill["discrepancies"] == []
    # Explanation and category suggestion are attached (deterministic fallbacks).
    assert bill["explanation"]["bill_summary"]
    assert bill["category"]["name"]


def test_process_flags_provable_sum_mismatch(client):
    resp = client.post("/bills:process", data={"text": BROKEN_BILL_TEXT}, headers=_auth())
    assert resp.status_code == 200
    bill = resp.json()
    assert bill["discrepancies"], "826 expected vs 900 printed must be flagged"
    # The flag carries the conflicting figures as evidence, not just a verdict.
    evidence = str(bill["discrepancies"][0])
    assert "900" in evidence


def test_process_declines_non_bill_text_honestly(client):
    resp = client.post(
        "/bills:process",
        data={"text": "hello there, this is just a friendly note with no amounts"},
        headers=_auth(),
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["declined"] is True
    assert body["reason"]


# --- abuse guardrails over HTTP ------------------------------------------------


def test_llm_endpoints_hit_stricter_budget(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_llm_per_minute", 2)
    rate_limit.reset_limiters()

    for _ in range(2):
        resp = client.post("/bills:process", data={"text": BILL_TEXT}, headers=_auth())
        assert resp.status_code == 200
    resp = client.post("/bills:process", data={"text": BILL_TEXT}, headers=_auth())
    assert resp.status_code == 429
    assert int(resp.headers["Retry-After"]) >= 1
    assert resp.json()["error"] == "rate_limited"


def test_standard_budget_covers_all_user_routes(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 3)
    rate_limit.reset_limiters()
    monkeypatch.setattr(persistence, "select", lambda *a, **k: [])

    for _ in range(3):
        assert client.get("/bills", headers=_auth()).status_code == 200
    assert client.get("/bills", headers=_auth()).status_code == 429


def test_rate_limit_is_per_caller_not_global(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 1)
    rate_limit.reset_limiters()
    monkeypatch.setattr(persistence, "select", lambda *a, **k: [])

    assert client.get("/bills", headers=_auth("user-a")).status_code == 200
    assert client.get("/bills", headers=_auth("user-a")).status_code == 429
    # A different signed-in user has their own budget.
    assert client.get("/bills", headers=_auth("user-b")).status_code == 200


def test_oversized_upload_is_refused_before_processing(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_request_mb", 0)
    resp = client.post("/bills:process", data={"text": BILL_TEXT}, headers=_auth())
    assert resp.status_code == 413
    assert resp.json()["error"] == "request_too_large"


def test_meta_routes_are_never_throttled(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 1)
    rate_limit.reset_limiters()
    for _ in range(5):
        assert client.get("/health").status_code == 200

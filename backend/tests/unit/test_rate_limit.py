"""Abuse guardrails: the sliding-window limiter itself (pure, in-memory)."""

from __future__ import annotations

import time

from src.services.rate_limit import SlidingWindowLimiter


def test_allows_up_to_limit_then_blocks():
    limiter = SlidingWindowLimiter(limit=3, window_seconds=60.0)
    assert limiter.acquire("u1") == 0.0
    assert limiter.acquire("u1") == 0.0
    assert limiter.acquire("u1") == 0.0
    retry = limiter.acquire("u1")
    assert 0.0 < retry <= 60.0


def test_keys_are_independent_buckets():
    limiter = SlidingWindowLimiter(limit=1, window_seconds=60.0)
    assert limiter.acquire("u1") == 0.0
    assert limiter.acquire("u1") > 0.0  # u1 exhausted
    assert limiter.acquire("u2") == 0.0  # u2 unaffected


def test_window_expiry_frees_budget():
    limiter = SlidingWindowLimiter(limit=1, window_seconds=0.05)
    assert limiter.acquire("u1") == 0.0
    assert limiter.acquire("u1") > 0.0
    time.sleep(0.06)
    assert limiter.acquire("u1") == 0.0


def test_reset_clears_all_counters():
    limiter = SlidingWindowLimiter(limit=1, window_seconds=60.0)
    limiter.acquire("u1")
    assert limiter.acquire("u1") > 0.0
    limiter.reset()
    assert limiter.acquire("u1") == 0.0

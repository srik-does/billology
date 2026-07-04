"""Abuse guardrails at the trust boundary: rate limiting + request-size caps.

Every authenticated route ultimately spends money (LLM calls) or database
capacity, so the API enforces two per-caller sliding-window limits:

- a standard limit for all ``/bills``, ``/dashboard`` and ``/qa`` traffic
  (``RATE_LIMIT_PER_MINUTE``, default 60/min), and
- a stricter limit for the LLM-heavy endpoints — bill extraction and Q&A —
  (``RATE_LIMIT_LLM_PER_MINUTE``, default 10/min),

plus a request-body size cap (``MAX_REQUEST_MB``, default 15 MB) so an
oversized upload is refused before it is read into memory.

Callers are keyed by their bearer token (hashed — one signed-in user is one
bucket regardless of IP), falling back to the client IP for unauthenticated
requests so failed-auth floods are also throttled.

The store is in-process memory: correct for the current single-instance
deployment (one uvicorn worker on Render), and the right first line of defense
even behind a shared store. Scaling to multiple replicas requires moving the
counters to a shared backend (e.g. Redis) — see the deployment notes.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse

from src.config import get_settings

# Paths subject to the guardrails (everything user-facing / data-bearing).
LIMITED_PREFIXES = ("/bills", "/dashboard", "/qa")
# LLM-heavy operations: vision/LLM extraction and question answering.
EXPENSIVE_PATHS = frozenset({"/bills:process", "/qa"})

# Purge idle buckets once the store crosses this many keys (keeps memory flat
# under an IP-rotating flood instead of growing without bound).
_PURGE_THRESHOLD = 10_000


class SlidingWindowLimiter:
    """Thread-safe sliding-window counter: at most ``limit`` hits per window."""

    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def acquire(self, key: str) -> float:
        """Record a hit for ``key``. Returns 0 if allowed, else seconds to wait."""
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] >= self.window:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return self.window - (now - bucket[0])
            bucket.append(now)
            if len(self._hits) > _PURGE_THRESHOLD:
                self._purge(now)
            return 0.0

    def _purge(self, now: float) -> None:
        stale = [k for k, b in self._hits.items() if not b or now - b[-1] >= self.window]
        for key in stale:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


_lock = threading.Lock()
_standard: Optional[SlidingWindowLimiter] = None
_expensive: Optional[SlidingWindowLimiter] = None


def _limiters() -> tuple[SlidingWindowLimiter, SlidingWindowLimiter]:
    """Lazily build the two shared limiters from settings (once)."""
    global _standard, _expensive
    with _lock:
        if _standard is None or _expensive is None:
            settings = get_settings()
            _standard = SlidingWindowLimiter(settings.rate_limit_per_minute)
            _expensive = SlidingWindowLimiter(settings.rate_limit_llm_per_minute)
        return _standard, _expensive


def reset_limiters() -> None:
    """Drop all counters and re-read limits from settings (tests / reconfig)."""
    global _standard, _expensive
    with _lock:
        _standard = None
        _expensive = None


def _caller_key(request: Request) -> str:
    """One bucket per signed-in user (hashed token), else per client IP."""
    bearer = request.headers.get("authorization") or ""
    if bearer:
        return "t:" + hashlib.sha256(bearer.encode()).hexdigest()[:16]
    return "ip:" + (request.client.host if request.client else "unknown")


def enforce(request: Request) -> Optional[JSONResponse]:
    """Apply size + rate guardrails. Returns the refusal response, or None.

    Runs in middleware before any body is read, so an oversized or throttled
    request costs nothing beyond this check.
    """
    path = request.url.path
    if not path.startswith(LIMITED_PREFIXES):
        return None

    settings = get_settings()

    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit():
        max_bytes = settings.max_request_mb * 1024 * 1024
        if int(content_length) > max_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "error": "request_too_large",
                    "detail": (
                        f"Request body exceeds the {settings.max_request_mb} MB limit. "
                        "Try a smaller photo or a lower-resolution scan."
                    ),
                },
            )

    standard, expensive = _limiters()
    key = _caller_key(request)
    retry_after = standard.acquire(key)
    if not retry_after and path in EXPENSIVE_PATHS and request.method == "POST":
        retry_after = expensive.acquire(key)
    if retry_after:
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limited",
                "detail": "Too many requests — please wait a moment and try again.",
            },
            headers={"Retry-After": str(max(1, int(retry_after + 0.999)))},
        )
    return None

"""In-memory sliding-window rate limiter (per client IP)."""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable

from flask import Flask, g, request
from werkzeug.exceptions import TooManyRequests


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int  # seconds until the next request would be allowed (0 if allowed)


class RateLimiter:
    """Allows at most `limit` requests per `window` seconds for each key.

    Keeps the timestamps of accepted requests in the last window (a sliding
    log), so there is no burst at window boundaries as with fixed windows.
    Rejected requests are not recorded and do not extend the block.
    """

    def __init__(self, limit: int = 100, window: float = 60.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.limit = limit
        self.window = window
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._calls_since_cleanup = 0

    def hit(self, key: str) -> RateLimitResult:
        now = self._clock()
        with self._lock:
            self._maybe_cleanup(now)
            hits = self._hits.setdefault(key, deque())
            self._expire(hits, now)

            if len(hits) >= self.limit:
                retry_after = max(1, math.ceil(hits[0] + self.window - now))
                return RateLimitResult(False, self.limit, 0, retry_after)

            hits.append(now)
            return RateLimitResult(True, self.limit, self.limit - len(hits), 0)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def _expire(self, hits: deque[float], now: float) -> None:
        while hits and hits[0] <= now - self.window:
            hits.popleft()

    def _maybe_cleanup(self, now: float) -> None:
        """Drop idle clients now and then so memory doesn't grow without bound."""
        self._calls_since_cleanup += 1
        if self._calls_since_cleanup < 1000:
            return
        self._calls_since_cleanup = 0
        for key in list(self._hits):
            self._expire(self._hits[key], now)
            if not self._hits[key]:
                del self._hits[key]


def init_rate_limiter(app: Flask) -> RateLimiter | None:
    """Apply the limiter to every request, configured from app.config:

    RATE_LIMIT_ENABLED (default True), RATE_LIMIT (100), RATE_LIMIT_WINDOW (60 s).
    """
    if not app.config.get("RATE_LIMIT_ENABLED", True):
        return None

    limiter = RateLimiter(app.config.get("RATE_LIMIT", 100),
                          app.config.get("RATE_LIMIT_WINDOW", 60))
    app.extensions["rate_limiter"] = limiter

    @app.before_request
    def enforce_rate_limit():
        # remote_addr is the direct client. Behind a reverse proxy, wrap the app
        # in werkzeug's ProxyFix instead of trusting X-Forwarded-For blindly.
        result = limiter.hit(request.remote_addr or "unknown")
        g.rate_limit = result
        if not result.allowed:
            raise TooManyRequests(
                description=(f"Rate limit of {result.limit} requests per "
                             f"{limiter.window:g} seconds exceeded. "
                             f"Retry in {result.retry_after} seconds."),
                retry_after=result.retry_after,
            )

    @app.after_request
    def add_rate_limit_headers(response):
        result = g.get("rate_limit")
        if result is not None:
            response.headers["X-RateLimit-Limit"] = str(result.limit)
            response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        return response

    return limiter

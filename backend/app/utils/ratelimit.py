"""Small in-memory sliding-window rate limiter (per process).

Good enough to stop a single client from burning your AI-provider quota. With N uvicorn workers the
effective limit is N x the configured value; put a CDN / reverse proxy limiter in front for strict limits.
"""
from __future__ import annotations

import time
from collections import deque


class RateLimiter:
    def __init__(self, window_seconds: float = 60.0, max_keys: int = 10_000):
        self.window, self.max_keys = window_seconds, max_keys
        self._hits: dict[str, deque[float]] = {}

    def check(self, key: str, limit: int, now: float | None = None) -> tuple[bool, int]:
        """Record a hit. Returns (allowed, retry_after_seconds). limit <= 0 disables limiting."""
        if limit <= 0:
            return True, 0
        now = time.monotonic() if now is None else now
        q = self._hits.setdefault(key, deque())
        cutoff = now - self.window
        while q and q[0] <= cutoff:
            q.popleft()
        if len(q) >= limit:
            return False, max(1, int(q[0] + self.window - now) + 1)
        q.append(now)
        if len(self._hits) > self.max_keys:  # bound memory: drop idle keys
            for k in [k for k, v in self._hits.items() if not v or v[-1] <= cutoff]:
                self._hits.pop(k, None)
        return True, 0

"""A small in-memory rate limiter (one backend process is enough for the hackathon).

The Quick Tunnel URL is public, so expensive endpoints are limited per client. Behind Cloudflare
the client address arrives in CF-Connecting-IP; behind the Vite proxy in X-Forwarded-For.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


def client_key(request: Request) -> str:
    for header in ("cf-connecting-ip", "x-forwarded-for"):
        value = request.headers.get(header)
        if value:
            return value.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    def __init__(self, limit: int, window_s: float) -> None:
        self.limit, self.window_s = limit, window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window_s:
                hits.popleft()
            if len(hits) >= self.limit:
                retry = int(self.window_s - (now - hits[0])) + 1
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many requests. Please try again in about {retry} seconds.",
                    headers={"Retry-After": str(retry)},
                )
            hits.append(now)

    def __call__(self, request: Request) -> None:  # FastAPI dependency
        self.check(client_key(request))

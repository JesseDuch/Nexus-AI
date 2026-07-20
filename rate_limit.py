"""Simple in-memory sliding-window rate limiter (per identity: user / api key / IP)."""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from .config import get_settings

settings = get_settings()

_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def check_rate_limit(identity: str, limit_per_minute: int | None = None) -> None:
    limit = limit_per_minute or settings.rate_limit_per_minute
    now = time.monotonic()
    window_start = now - 60.0
    with _lock:
        q = _hits[identity]
        while q and q[0] < window_start:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": {
                        "message": f"Rate limit exceeded ({limit} requests/min). Slow down and retry.",
                        "type": "rate_limit_error",
                        "code": "rate_limit_exceeded",
                    }
                },
            )
        q.append(now)


def identity_from_request(request: Request, suffix: str) -> str:
    return f"{suffix}:{request.client.host if request.client else 'unknown'}"

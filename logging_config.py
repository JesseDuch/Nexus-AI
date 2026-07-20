"""Structured JSON logging + per-request audit middleware (roadmap 7.2)."""
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .database import SessionLocal
from .models import AuditLog


def configure_logging() -> None:
    """Single-line JSON access log to stdout (container-friendly)."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger("nexusai")
    root.setLevel(logging.INFO)
    root.propagate = False
    if not root.handlers:
        root.addHandler(handler)


logger = logging.getLogger("nexusai")


class AuditMiddleware(BaseHTTPMiddleware):
    """Assigns a request-id, times the call, writes an AuditLog row, and emits a
    structured JSON log line for /api + /v1 routes (skips static/media)."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not (path.startswith("/api") or path.startswith("/v1")):
            return await call_next(request)

        request_id = uuid.uuid4().hex[:16]
        start = time.monotonic()
        response = await call_next(request)
        latency_ms = int((time.monotonic() - start) * 1000)
        response.headers["X-Request-ID"] = request_id

        user_id = getattr(request.state, "user_id", None)
        api_key_id = getattr(request.state, "api_key_id", None)
        try:
            with SessionLocal() as s:
                s.add(
                    AuditLog(
                        request_id=request_id,
                        user_id=user_id,
                        api_key_id=api_key_id,
                        method=request.method,
                        path=path[:255],
                        status_code=response.status_code,
                        latency_ms=latency_ms,
                        ip=request.client.host if request.client else "",
                    )
                )
                s.commit()
        except Exception:
            pass  # auditing must never break the request path

        logger.info(
            __import__("json").dumps(
                {
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "request_id": request_id,
                    "method": request.method,
                    "path": path,
                    "status": response.status_code,
                    "latency_ms": latency_ms,
                    "user_id": user_id,
                }
            )
        )
        return response

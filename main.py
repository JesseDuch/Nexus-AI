"""NexusAI platform — FastAPI central hub (Phase 1).

Serves:
  • OpenAI-compatible developer API  (/v1/chat/completions, /v1/models)
  • Web console backend              (/api/auth, /api/keys, /api/user, /api/conversations, /api/chat)
  • Built React console (static SPA) if frontend dist is present
"""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import Base, engine
from .logging_config import AuditMiddleware, configure_logging
from .routers import admin, auth, conversations, feedback, internal, keys, media, openai_v1, user

configure_logging()
settings = get_settings()

# Create tables (Alembic can replace this once the schema stabilizes).
Base.metadata.create_all(bind=engine)


def _run_lightweight_migrations() -> None:
    """Add columns introduced after initial release (idempotent, SQLite/Postgres)."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "usage_records" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("usage_records")}
        with engine.begin() as conn:
            if "media_count" not in cols:
                conn.execute(text("ALTER TABLE usage_records ADD COLUMN media_count INTEGER DEFAULT 0"))
            if "media_type" not in cols:
                conn.execute(text("ALTER TABLE usage_records ADD COLUMN media_type VARCHAR(20) DEFAULT ''"))


_run_lightweight_migrations()

app = FastAPI(
    title=f"{settings.platform_name} API",
    description="OpenAI-compatible AI platform — GLM text/code backend, FastAPI gateway.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuditMiddleware)


# ---------------- error normalization ----------------

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": {"message": "Invalid request body", "type": "invalid_request_error", "details": exc.errors()[:5]}},
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": {"message": "Internal server error", "type": "server_error"}},
    )


# ---------------- routers ----------------

app.include_router(auth.router)
app.include_router(keys.router)
app.include_router(user.router)
app.include_router(conversations.router)
app.include_router(media.router)
app.include_router(internal.router)
app.include_router(admin.router)
app.include_router(feedback.router)
app.include_router(openai_v1.router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "platform": settings.platform_name,
        "glm_configured": bool(settings.glm_api_key),
        "image_backend": settings.image_backend,
        "video_backend": settings.video_backend,
        "sandbox_backend": settings.sandbox_backend,
        "tf_agent_policy": bool(settings.tf_agent_policy_path),
    }


@app.get("/api/metrics")
def metrics():
    """Lightweight runtime metrics for monitoring (roadmap 9.2)."""
    import time

    from sqlalchemy import func as _func

    from .database import SessionLocal
    from .models import AuditLog, UsageRecord

    uptime = int(time.monotonic())
    with SessionLocal() as s:
        requests_24h = s.query(_func.count(AuditLog.id)).scalar() or 0
        tokens_total = int(s.query(_func.coalesce(_func.sum(UsageRecord.total_tokens), 0)).scalar() or 0)
        media_total = int(s.query(_func.coalesce(_func.sum(UsageRecord.media_count), 0)).scalar() or 0)
    return {
        "uptime_seconds": uptime,
        "requests_logged": int(requests_24h),
        "tokens_total": tokens_total,
        "media_total": media_total,
        "glm_configured": bool(settings.glm_api_key),
        "backends": {
            "image": settings.image_backend,
            "video": settings.video_backend,
            "sandbox": settings.sandbox_backend,
        },
    }


# ---------------- generated media (public URLs) ----------------

_media_dir = Path(settings.media_dir).resolve()
_media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=_media_dir), name="media")


# ---------------- static SPA (React console) ----------------

_dist = Path(settings.frontend_dist).resolve()
if _dist.is_dir():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        # API routes are handled above; everything else serves the console.
        target = (_dist / full_path).resolve()
        if full_path and target.is_file() and str(target).startswith(str(_dist)):
            return FileResponse(target)
        return FileResponse(_dist / "index.html")

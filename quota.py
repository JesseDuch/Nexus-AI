"""Per-user daily quota enforcement (roadmap 7.1)."""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import get_settings
from .models import UsageRecord

settings = get_settings()


def _today_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def today_usage(db: Session, user_id: int) -> dict:
    start = _today_start()
    tokens, media, code_exec = (
        db.query(
            func.coalesce(func.sum(UsageRecord.total_tokens), 0),
            func.coalesce(func.sum(UsageRecord.media_count).filter(UsageRecord.media_type.in_(["image", "video"])), 0),
            func.coalesce(func.sum(UsageRecord.media_count).filter(UsageRecord.media_type == "code_exec"), 0),
        )
        .filter(UsageRecord.user_id == user_id, UsageRecord.created_at >= start)
        .one()
    )
    return {"tokens": int(tokens), "media": int(media), "code_exec": int(code_exec)}


def check_quota(db: Session, user_id: int, kind: str) -> None:
    """Raise 429 when the user exceeds the daily quota for `kind`
    (tokens / media / code_exec)."""
    usage = today_usage(db, user_id)
    limits = {
        "tokens": (settings.daily_token_quota, usage["tokens"]),
        "media": (settings.daily_media_quota, usage["media"]),
        "code_exec": (settings.daily_code_exec_quota, usage["code_exec"]),
    }
    limit, used = limits[kind]
    if used >= limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": {
                    "message": f"Daily {kind} quota exceeded ({used}/{limit}). Resets at midnight UTC.",
                    "type": "quota_exceeded",
                    "code": "daily_quota_exceeded",
                }
            },
        )

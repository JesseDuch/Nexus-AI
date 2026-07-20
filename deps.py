"""FastAPI dependencies: current-user (JWT) and api-key auth, plus helpers."""
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import ApiKey, User
from .security import decode_jwt, hash_api_key

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    """Web-console auth via JWT."""
    if creds is None:
        raise HTTPException(status_code=401, detail="Missing authorization token")
    user_id = decode_jwt(creds.credentials)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    request.state.user_id = user.id
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Admin-only gate for /api/admin routes."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def get_api_key_context(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> tuple[User, ApiKey]:
    """Public /v1 developer API auth via platform API key (sk-nx-...)."""
    if creds is None or not creds.credentials.startswith("sk-"):
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": "Missing or malformed API key. Provide `Authorization: Bearer sk-...`.",
                    "type": "invalid_request_error",
                    "code": "invalid_api_key",
                }
            },
        )
    key_hash = hash_api_key(creds.credentials)
    api_key = db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
    if api_key is None or api_key.revoked:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": "Invalid or revoked API key.",
                    "type": "invalid_request_error",
                    "code": "invalid_api_key",
                }
            },
        )
    api_key.last_used_at = datetime.now(timezone.utc)
    db.commit()
    request.state.user_id = api_key.user_id
    request.state.api_key_id = api_key.id
    return api_key.user, api_key

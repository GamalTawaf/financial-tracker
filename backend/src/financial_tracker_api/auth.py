"""Password hashing and JWT helpers."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlmodel import Session, select

from financial_tracker_api.config import get_settings
from financial_tracker_api.models import RefreshSession

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"

_PASSWORD_RULES = [
    (r".{12,}", "at least 12 characters"),
    (r"[A-Z]", "an uppercase letter"),
    (r"[a-z]", "a lowercase letter"),
    (r"[0-9]", "a digit"),
]


def validate_password_strength(password: str) -> None:
    """Raise ValueError listing unmet password rules."""
    missing = [label for pattern, label in _PASSWORD_RULES if not re.search(pattern, password)]
    if missing:
        raise ValueError("Password must include " + ", ".join(missing))


def hash_password(password: str) -> str:
    """Hash a plaintext password."""
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a hash."""
    return pwd_context.verify(password, password_hash)


def create_access_token(subject: str) -> str:
    """Create a short-lived access JWT for the given subject (user id)."""
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire, "typ": "access"}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def issue_refresh_session(session: Session, user_id: int) -> str:
    """Persist a refresh session and return the refresh JWT."""
    settings = get_settings()
    jti = uuid4().hex
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    session.add(RefreshSession(user_id=user_id, jti=jti, expires_at=expires_at))
    session.commit()
    payload = {
        "sub": str(user_id),
        "exp": expires_at,
        "typ": "refresh",
        "jti": jti,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_token_pair(session: Session, user_id: int) -> tuple[str, str, int]:
    """Return (access, refresh, access_expires_in_seconds)."""
    settings = get_settings()
    access = create_access_token(str(user_id))
    refresh = issue_refresh_session(session, user_id)
    return access, refresh, settings.access_token_expire_minutes * 60


def decode_access_token(token: str) -> str | None:
    """Return subject from an access JWT, or None if invalid."""
    payload = _decode_token(token)
    if payload is None or payload.get("typ") != "access":
        return None
    subject = payload.get("sub")
    return str(subject) if subject is not None else None


def rotate_refresh_token(session: Session, token: str) -> tuple[str, str, int] | None:
    """Validate refresh token, revoke it, and issue a new pair."""
    payload = _decode_token(token)
    if payload is None or payload.get("typ") != "refresh":
        return None
    jti = payload.get("jti")
    subject = payload.get("sub")
    if not jti or subject is None:
        return None
    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        return None
    row = session.exec(
        select(RefreshSession).where(
            RefreshSession.jti == jti,
            RefreshSession.user_id == user_id,
        )
    ).first()
    if row is None or row.revoked:
        return None
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < datetime.now(UTC):
        row.revoked = True
        session.add(row)
        session.commit()
        return None
    row.revoked = True
    session.add(row)
    session.commit()
    return create_token_pair(session, user_id)


def revoke_refresh_token(session: Session, token: str) -> bool:
    """Revoke a refresh token if present."""
    payload = _decode_token(token)
    if payload is None or payload.get("typ") != "refresh":
        return False
    jti = payload.get("jti")
    if not jti:
        return False
    row = session.exec(select(RefreshSession).where(RefreshSession.jti == jti)).first()
    if row is None:
        return False
    row.revoked = True
    session.add(row)
    session.commit()
    return True


def _decode_token(token: str) -> dict | None:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None

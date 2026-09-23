from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.shopfilter_api.models import AuthSessionRecord, UserRecord

SESSION_COOKIE_NAME = "shopfilter_session"
_PASSWORD_HASHER = PasswordHasher()
_DUMMY_PASSWORD_HASH = _PASSWORD_HASHER.hash("shopfilter-dummy-password")


class MembershipRole(StrEnum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    ENGINEER = "ENGINEER"
    REVIEWER = "REVIEWER"
    VIEWER = "VIEWER"


@dataclass(frozen=True)
class CreatedSession:
    raw_token: str
    record: AuthSessionRecord


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def hash_password(password: str) -> str:
    if len(password) < 12 or len(password) > 1024:
        raise ValueError("Password must contain 12 to 1024 characters")
    return _PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(password_hash, password)
    except VerificationError:
        return False


def session_token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def authenticate_user(session: Session, email: str, password: str) -> UserRecord | None:
    user = session.scalar(
        select(UserRecord).where(UserRecord.email == normalize_email(email))
    )
    candidate_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    valid = verify_password(candidate_hash, password)
    if user is None or not valid or not user.is_active:
        return None
    return user


def create_session(
    session: Session, user: UserRecord, *, duration: timedelta
) -> CreatedSession:
    raw_token = secrets.token_urlsafe(32)
    record = AuthSessionRecord(
        user_id=user.id,
        token_hash=session_token_hash(raw_token),
        expires_at=datetime.now(UTC) + duration,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return CreatedSession(raw_token=raw_token, record=record)

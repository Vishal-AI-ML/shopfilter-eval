from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.api.shopfilter_api.auth import SESSION_COOKIE_NAME, session_token_hash
from services.api.shopfilter_api.models import AuthSessionRecord, UserRecord


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.database.session() as session:
        yield session


DbSession = Annotated[Session, Depends(get_session)]


@dataclass(frozen=True)
class AuthenticatedSession:
    user: UserRecord
    record: AuthSessionRecord


def get_authenticated_session(
    request: Request, session: DbSession
) -> AuthenticatedSession:
    raw_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    record = session.scalar(
        select(AuthSessionRecord)
        .join(UserRecord)
        .where(
            AuthSessionRecord.token_hash == session_token_hash(raw_token),
            AuthSessionRecord.revoked_at.is_(None),
            AuthSessionRecord.expires_at > func.now(),
            UserRecord.is_active.is_(True),
        )
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    user = session.get(UserRecord, record.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return AuthenticatedSession(user=user, record=record)


CurrentSession = Annotated[AuthenticatedSession, Depends(get_authenticated_session)]


def get_current_user(authenticated: CurrentSession) -> UserRecord:
    return authenticated.user


CurrentUser = Annotated[UserRecord, Depends(get_current_user)]


def get_organization_id(
    x_organization_id: Annotated[str | None, Header()] = None,
) -> uuid.UUID:
    if x_organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Organization-ID header is required",
        )
    try:
        return uuid.UUID(x_organization_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Organization-ID must be a valid UUID",
        ) from exc

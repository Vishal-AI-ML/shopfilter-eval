from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.api.shopfilter_api.auth import (
    SESSION_COOKIE_NAME,
    MembershipRole,
    session_token_hash,
)
from services.api.shopfilter_api.models import (
    AuthSessionRecord,
    MembershipRecord,
    UserRecord,
)


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


@dataclass(frozen=True)
class OrganizationAccess:
    organization_id: uuid.UUID
    user: UserRecord
    membership: MembershipRecord
    role: MembershipRole


def _organization_header(
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


def get_organization_access(
    organization_id: Annotated[uuid.UUID, Depends(_organization_header)],
    current_user: CurrentUser,
    session: DbSession,
) -> OrganizationAccess:
    membership = session.scalar(
        select(MembershipRecord).where(
            MembershipRecord.organization_id == organization_id,
            MembershipRecord.user_id == current_user.id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrganizationAccess(
        organization_id=organization_id,
        user=current_user,
        membership=membership,
        role=MembershipRole(membership.role),
    )


OrganizationContext = Annotated[OrganizationAccess, Depends(get_organization_access)]


def get_organization_id(access: OrganizationContext) -> uuid.UUID:
    return access.organization_id


def require_resource_write(access: OrganizationContext) -> OrganizationAccess:
    allowed = {
        MembershipRole.OWNER,
        MembershipRole.ADMIN,
        MembershipRole.ENGINEER,
    }
    if access.role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role for this operation",
        )
    return access


ResourceWriter = Annotated[OrganizationAccess, Depends(require_resource_write)]

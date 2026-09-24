from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.shopfilter_api.auth import (
    SESSION_COOKIE_NAME,
    MembershipRole,
    authenticate_user,
    create_session,
    hash_password,
)
from services.api.shopfilter_api.auth_schemas import (
    AuthenticatedUserResponse,
    LoginRequest,
    LoginResponse,
    MembershipResponse,
    RegistrationRequest,
)
from services.api.shopfilter_api.dependencies import (
    CurrentSession,
    CurrentUser,
    get_session,
)
from services.api.shopfilter_api.models import (
    MembershipRecord,
    Organization,
    UserRecord,
)

router = APIRouter(prefix="/v1/auth", tags=["authentication"])
DbSession = Annotated[Session, Depends(get_session)]


def _user_response(session: Session, user: UserRecord) -> AuthenticatedUserResponse:
    memberships = list(
        session.scalars(
            select(MembershipRecord)
            .where(MembershipRecord.user_id == user.id)
            .order_by(MembershipRecord.organization_id)
        ).all()
    )
    return AuthenticatedUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        memberships=[MembershipResponse.model_validate(item) for item in memberships],
    )


def _set_session_cookie(
    response: Response,
    *,
    raw_token: str,
    duration: timedelta,
    secure: bool,
) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_token,
        max_age=int(duration.total_seconds()),
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: RegistrationRequest,
    request: Request,
    response: Response,
    session: DbSession,
) -> LoginResponse:
    organization = Organization(
        name=body.organization_name,
        slug=body.organization_slug,
    )
    user = UserRecord(
        email=body.email,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        is_active=True,
    )
    session.add_all([organization, user])

    settings = request.app.state.settings
    duration = timedelta(hours=settings.session_duration_hours)
    try:
        session.flush()
        session.add(
            MembershipRecord(
                organization_id=organization.id,
                user_id=user.id,
                role=MembershipRole.OWNER.value,
            )
        )
        created = create_session(session, user, duration=duration)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to create account with those details",
        ) from exc

    _set_session_cookie(
        response,
        raw_token=created.raw_token,
        duration=duration,
        secure=settings.session_cookie_secure,
    )
    return LoginResponse(
        user=_user_response(session, user),
        expires_at=created.record.expires_at,
    )


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: DbSession,
) -> LoginResponse:
    user = authenticate_user(session, body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    settings = request.app.state.settings
    duration = timedelta(hours=settings.session_duration_hours)
    created = create_session(session, user, duration=duration)
    _set_session_cookie(
        response,
        raw_token=created.raw_token,
        duration=duration,
        secure=settings.session_cookie_secure,
    )
    return LoginResponse(
        user=_user_response(session, user),
        expires_at=created.record.expires_at,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    authenticated: CurrentSession,
    session: DbSession,
) -> None:
    authenticated.record.revoked_at = datetime.now(UTC)
    session.commit()
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


@router.get("/me", response_model=AuthenticatedUserResponse)
def me(current_user: CurrentUser, session: DbSession) -> AuthenticatedUserResponse:
    return _user_response(session, current_user)

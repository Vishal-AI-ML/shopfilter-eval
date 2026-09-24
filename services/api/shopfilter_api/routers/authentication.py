from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.shopfilter_api.auth import (
    SESSION_COOKIE_NAME,
    MembershipRole,
    authenticate_user,
    create_session,
    email_verification_token_hash,
    hash_password,
    invitation_token_hash,
    password_reset_token_hash,
    verify_password,
)
from services.api.shopfilter_api.auth_schemas import (
    AuthenticatedUserResponse,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MembershipResponse,
    MessageResponse,
    RegistrationRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from services.api.shopfilter_api.dependencies import (
    CurrentSession,
    CurrentUser,
    get_session,
)
from services.api.shopfilter_api.email_verification_mailer import (
    EmailVerificationDeliveryError,
)
from services.api.shopfilter_api.invitation_schemas import InvitationAcceptRequest
from services.api.shopfilter_api.models import (
    AuthSessionRecord,
    EmailVerificationTokenRecord,
    MembershipRecord,
    Organization,
    OrganizationInvitationRecord,
    PasswordResetTokenRecord,
    UserRecord,
)
from services.api.shopfilter_api.password_reset_mailer import (
    PasswordResetDeliveryError,
)

router = APIRouter(prefix="/v1/auth", tags=["authentication"])
logger = logging.getLogger(__name__)
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
        email_verified=user.email_verified_at is not None,
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


def _issue_email_verification(
    request: Request, session: Session, user: UserRecord, *, now: datetime
) -> EmailVerificationTokenRecord:
    session.execute(
        update(EmailVerificationTokenRecord)
        .where(
            EmailVerificationTokenRecord.user_id == user.id,
            EmailVerificationTokenRecord.used_at.is_(None),
        )
        .values(used_at=now)
    )
    raw_token = secrets.token_urlsafe(32)
    record = EmailVerificationTokenRecord(
        user_id=user.id,
        token_hash=email_verification_token_hash(raw_token),
        expires_at=now
        + timedelta(
            minutes=request.app.state.settings.email_verification_expiry_minutes
        ),
    )
    session.add(record)
    session.commit()

    base_url = request.app.state.settings.public_web_url.rstrip("/")
    verification_url = f"{base_url}/verify-email?token={quote(raw_token)}"
    try:
        request.app.state.email_verification_mailer.send(
            recipient=user.email,
            display_name=user.display_name,
            verification_url=verification_url,
        )
    except EmailVerificationDeliveryError:
        record.used_at = datetime.now(UTC)
        session.commit()
        logger.warning("Email verification delivery failed")
    return record


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
        email_verified_at=None,
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

    _issue_email_verification(request, session, user, now=datetime.now(UTC))
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


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def resend_verification(
    request: Request, current_user: CurrentUser, session: DbSession
) -> MessageResponse:
    message = MessageResponse(
        message="If verification is still required, a new link has been sent."
    )
    if current_user.email_verified_at is not None:
        return message
    _issue_email_verification(request, session, current_user, now=datetime.now(UTC))
    return message


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(body: VerifyEmailRequest, session: DbSession) -> MessageResponse:
    now = datetime.now(UTC)
    record = session.scalar(
        select(EmailVerificationTokenRecord)
        .where(
            EmailVerificationTokenRecord.token_hash
            == email_verification_token_hash(body.token),
            EmailVerificationTokenRecord.used_at.is_(None),
            EmailVerificationTokenRecord.expires_at > now,
        )
        .with_for_update()
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired email verification link",
        )
    user = session.get(UserRecord, record.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired email verification link",
        )
    user.email_verified_at = now
    session.execute(
        update(EmailVerificationTokenRecord)
        .where(
            EmailVerificationTokenRecord.user_id == user.id,
            EmailVerificationTokenRecord.used_at.is_(None),
        )
        .values(used_at=now)
    )
    session.commit()
    return MessageResponse(message="Email verified successfully.")


@router.post("/accept-invitation", response_model=LoginResponse)
def accept_invitation(
    body: InvitationAcceptRequest,
    request: Request,
    response: Response,
    session: DbSession,
) -> LoginResponse:
    now = datetime.now(UTC)
    record = session.scalar(
        select(OrganizationInvitationRecord)
        .where(
            OrganizationInvitationRecord.token_hash == invitation_token_hash(body.token),
            OrganizationInvitationRecord.accepted_at.is_(None),
            OrganizationInvitationRecord.revoked_at.is_(None),
            OrganizationInvitationRecord.expires_at > now,
        )
        .with_for_update()
    )
    failure = HTTPException(status_code=400, detail="Unable to accept invitation")
    if record is None:
        raise failure
    user = session.scalar(select(UserRecord).where(UserRecord.email == record.email).with_for_update())
    if user is None:
        if body.display_name is None:
            raise failure
        user = UserRecord(email=record.email, display_name=body.display_name, password_hash=hash_password(body.password), is_active=True, email_verified_at=now)
        session.add(user)
        session.flush()
    elif not user.is_active or not verify_password(user.password_hash, body.password):
        raise failure
    else:
        user.email_verified_at = now
    if session.scalar(select(MembershipRecord.id).where(MembershipRecord.organization_id == record.organization_id, MembershipRecord.user_id == user.id)) is not None:
        raise failure
    session.add(MembershipRecord(organization_id=record.organization_id, user_id=user.id, role=record.role))
    record.accepted_at = now
    duration = timedelta(hours=request.app.state.settings.session_duration_hours)
    try:
        created = create_session(session, user, duration=duration)
    except IntegrityError as exc:
        session.rollback()
        raise failure from exc
    _set_session_cookie(response, raw_token=created.raw_token, duration=duration, secure=request.app.state.settings.session_cookie_secure)
    return LoginResponse(user=_user_response(session, user), expires_at=created.record.expires_at)


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    session: DbSession,
) -> MessageResponse:
    message = MessageResponse(
        message="If that account exists, a password reset link has been sent."
    )
    user = session.scalar(
        select(UserRecord).where(
            UserRecord.email == body.email,
            UserRecord.is_active.is_(True),
        )
    )
    if user is None:
        return message

    now = datetime.now(UTC)
    session.execute(
        update(PasswordResetTokenRecord)
        .where(
            PasswordResetTokenRecord.user_id == user.id,
            PasswordResetTokenRecord.used_at.is_(None),
        )
        .values(used_at=now)
    )
    raw_token = secrets.token_urlsafe(32)
    record = PasswordResetTokenRecord(
        user_id=user.id,
        token_hash=password_reset_token_hash(raw_token),
        expires_at=now
        + timedelta(minutes=request.app.state.settings.password_reset_expiry_minutes),
    )
    session.add(record)
    session.commit()

    base_url = request.app.state.settings.public_web_url.rstrip("/")
    reset_url = f"{base_url}/reset-password?token={quote(raw_token)}"
    try:
        request.app.state.password_reset_mailer.send(
            recipient=user.email,
            display_name=user.display_name,
            reset_url=reset_url,
        )
    except PasswordResetDeliveryError:
        record.used_at = datetime.now(UTC)
        session.commit()
        logger.warning("Password reset email delivery failed")
    return message


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(body: ResetPasswordRequest, session: DbSession) -> MessageResponse:
    new_password_hash = hash_password(body.password)
    now = datetime.now(UTC)
    record = session.scalar(
        select(PasswordResetTokenRecord)
        .where(
            PasswordResetTokenRecord.token_hash
            == password_reset_token_hash(body.token),
            PasswordResetTokenRecord.used_at.is_(None),
            PasswordResetTokenRecord.expires_at > now,
        )
        .with_for_update()
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset link",
        )
    user = session.get(UserRecord, record.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset link",
        )

    user.password_hash = new_password_hash
    session.execute(
        update(PasswordResetTokenRecord)
        .where(
            PasswordResetTokenRecord.user_id == user.id,
            PasswordResetTokenRecord.used_at.is_(None),
        )
        .values(used_at=now)
    )
    session.execute(
        update(AuthSessionRecord)
        .where(
            AuthSessionRecord.user_id == user.id,
            AuthSessionRecord.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    session.commit()
    return MessageResponse(message="Password reset successfully. Please sign in.")

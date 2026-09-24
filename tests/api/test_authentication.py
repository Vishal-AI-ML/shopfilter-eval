from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from email import policy
from email.parser import Parser
from typing import cast
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.api.shopfilter_api.auth import MembershipRole, hash_password
from services.api.shopfilter_api.email_verification_mailer import (
    FileEmailVerificationMailer,
    InMemoryEmailVerificationMailer,
)
from services.api.shopfilter_api.models import (
    AuthSessionRecord,
    EmailVerificationTokenRecord,
    MembershipRecord,
    Organization,
    PasswordResetTokenRecord,
    UserRecord,
)
from services.api.shopfilter_api.password_reset_mailer import (
    FilePasswordResetMailer,
    InMemoryPasswordResetMailer,
)

PASSWORD = "correct-horse-battery-staple"


def _identity(client: TestClient, *, active: bool = True) -> tuple[str, str]:
    app = cast(FastAPI, client.app)
    with Session(app.state.database.engine) as session:
        organization = Organization(name="Auth Organization", slug="auth-organization")
        user = UserRecord(
            email="owner@example.com",
            display_name="Owner User",
            password_hash=hash_password(PASSWORD),
            is_active=active,
            email_verified_at=datetime.now(UTC),
        )
        session.add_all([organization, user])
        session.flush()
        session.add(
            MembershipRecord(
                organization_id=organization.id,
                user_id=user.id,
                role=MembershipRole.OWNER.value,
            )
        )
        session.commit()
        return str(user.id), str(organization.id)


def test_login_me_and_logout_use_revocable_hashed_session(
    api_client: TestClient,
) -> None:
    user_id, organization_id = _identity(api_client)
    login = api_client.post(
        "/v1/auth/login",
        json={"email": " OWNER@EXAMPLE.COM ", "password": PASSWORD},
    )
    assert login.status_code == 200, login.text
    payload = login.json()
    assert payload["user"] == {
        "id": user_id,
        "email": "owner@example.com",
        "display_name": "Owner User",
        "is_active": True,
        "email_verified": True,
        "memberships": [
            {"organization_id": organization_id, "role": MembershipRole.OWNER.value}
        ],
    }
    assert "password" not in login.text.casefold()
    set_cookie = login.headers["set-cookie"].casefold()
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie

    app = cast(FastAPI, api_client.app)
    raw_token = api_client.cookies["shopfilter_session"]
    with Session(app.state.database.engine) as session:
        record = session.scalar(select(AuthSessionRecord))
        assert record is not None
        assert record.token_hash == hashlib.sha256(raw_token.encode()).hexdigest()
        assert raw_token not in record.token_hash
        assert session.scalar(select(func.count(AuthSessionRecord.id))) == 1

    current = api_client.get("/v1/auth/me")
    assert current.status_code == 200
    assert current.json()["id"] == user_id

    logout = api_client.post("/v1/auth/logout")
    assert logout.status_code == 204
    assert api_client.get("/v1/auth/me").status_code == 401
    with Session(app.state.database.engine) as session:
        record = session.scalar(select(AuthSessionRecord))
        assert record is not None
        assert record.revoked_at is not None


def test_invalid_credentials_return_one_generic_error(api_client: TestClient) -> None:
    _identity(api_client)
    wrong_password = api_client.post(
        "/v1/auth/login",
        json={"email": "owner@example.com", "password": "wrong-password"},
    )
    unknown_user = api_client.post(
        "/v1/auth/login",
        json={"email": "unknown@example.com", "password": "wrong-password"},
    )
    assert wrong_password.status_code == 401
    assert unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json() == {
        "detail": "Invalid email or password"
    }


def test_inactive_user_cannot_login(api_client: TestClient) -> None:
    _identity(api_client, active=False)
    response = api_client.post(
        "/v1/auth/login",
        json={"email": "owner@example.com", "password": PASSWORD},
    )
    assert response.status_code == 401


def test_expired_session_is_rejected(api_client: TestClient) -> None:
    _identity(api_client)
    login = api_client.post(
        "/v1/auth/login",
        json={"email": "owner@example.com", "password": PASSWORD},
    )
    assert login.status_code == 200
    app = cast(FastAPI, api_client.app)
    with Session(app.state.database.engine) as session:
        record = session.scalar(select(AuthSessionRecord))
        assert record is not None
        record.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()
    assert api_client.get("/v1/auth/me").status_code == 401


def test_password_hash_is_argon2_and_not_plaintext() -> None:
    encoded = hash_password(PASSWORD)
    assert encoded.startswith("$argon2id$")
    assert encoded != PASSWORD


def test_registration_atomically_creates_owner_organization_and_session(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/v1/auth/register",
        json={
            "display_name": " First Owner ",
            "email": " FIRST.OWNER@EXAMPLE.COM ",
            "password": PASSWORD,
            "organization_name": " First Commerce ",
            "organization_slug": "FIRST-COMMERCE",
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["user"]["email"] == "first.owner@example.com"
    assert payload["user"]["display_name"] == "First Owner"
    assert payload["user"]["email_verified"] is False
    assert payload["user"]["memberships"][0]["role"] == MembershipRole.OWNER.value
    assert "password" not in response.text.casefold()
    assert "httponly" in response.headers["set-cookie"].casefold()

    app = cast(FastAPI, api_client.app)
    with Session(app.state.database.engine) as session:
        user = session.scalar(
            select(UserRecord).where(UserRecord.email == "first.owner@example.com")
        )
        organization = session.scalar(
            select(Organization).where(Organization.slug == "first-commerce")
        )
        membership = session.scalar(select(MembershipRecord))
        auth_session = session.scalar(select(AuthSessionRecord))
        assert user is not None
        assert user.password_hash.startswith("$argon2id$")
        assert organization is not None
        assert organization.name == "First Commerce"
        assert membership is not None
        assert membership.user_id == user.id
        assert membership.organization_id == organization.id
        assert membership.role == MembershipRole.OWNER.value
        assert auth_session is not None
        assert auth_session.user_id == user.id

    current = api_client.get("/v1/auth/me")
    assert current.status_code == 200
    assert current.json()["id"] == payload["user"]["id"]


def test_registration_conflicts_use_one_safe_error_and_leave_no_partial_rows(
    api_client: TestClient,
) -> None:
    first = api_client.post(
        "/v1/auth/register",
        json={
            "display_name": "First Owner",
            "email": "first@example.com",
            "password": PASSWORD,
            "organization_name": "First Company",
            "organization_slug": "first-company",
        },
    )
    assert first.status_code == 201

    duplicate_email = api_client.post(
        "/v1/auth/register",
        json={
            "display_name": "Duplicate Email",
            "email": "first@example.com",
            "password": PASSWORD,
            "organization_name": "Another Company",
            "organization_slug": "another-company",
        },
    )
    duplicate_slug = api_client.post(
        "/v1/auth/register",
        json={
            "display_name": "Duplicate Slug",
            "email": "another@example.com",
            "password": PASSWORD,
            "organization_name": "First Company Again",
            "organization_slug": "first-company",
        },
    )
    expected = {"detail": "Unable to create account with those details"}
    assert duplicate_email.status_code == 409
    assert duplicate_slug.status_code == 409
    assert duplicate_email.json() == duplicate_slug.json() == expected

    app = cast(FastAPI, api_client.app)
    with Session(app.state.database.engine) as session:
        assert session.scalar(select(func.count(UserRecord.id))) == 1
        assert session.scalar(select(func.count(Organization.id))) == 1
        assert session.scalar(select(func.count(MembershipRecord.id))) == 1


def test_registration_rejects_weak_password_and_unknown_fields(
    api_client: TestClient,
) -> None:
    body = {
        "display_name": "New Owner",
        "email": "new@example.com",
        "password": "too-short",
        "organization_name": "New Company",
        "organization_slug": "new-company",
    }
    assert api_client.post("/v1/auth/register", json=body).status_code == 422
    body["password"] = PASSWORD
    body["unexpected"] = "value"
    assert api_client.post("/v1/auth/register", json=body).status_code == 422



def _reset_token(client: TestClient, email: str) -> str:
    app = cast(FastAPI, client.app)
    mailer = cast(InMemoryPasswordResetMailer, app.state.password_reset_mailer)
    assert len(mailer.messages) == 1
    assert mailer.messages[0].recipient == email
    values = parse_qs(urlparse(mailer.messages[0].reset_url).query)
    return values["token"][0]


def test_forgot_password_is_non_enumerating_and_stores_only_token_hash(
    api_client: TestClient,
) -> None:
    _identity(api_client)
    known = api_client.post(
        "/v1/auth/forgot-password", json={"email": "owner@example.com"}
    )
    unknown = api_client.post(
        "/v1/auth/forgot-password", json={"email": "unknown@example.com"}
    )
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()

    raw_token = _reset_token(api_client, "owner@example.com")
    app = cast(FastAPI, api_client.app)
    with Session(app.state.database.engine) as session:
        record = session.scalar(select(PasswordResetTokenRecord))
        assert record is not None
        assert record.token_hash == hashlib.sha256(raw_token.encode()).hexdigest()
        assert raw_token != record.token_hash


def test_password_reset_is_single_use_and_revokes_existing_sessions(
    api_client: TestClient,
) -> None:
    _identity(api_client)
    login = api_client.post(
        "/v1/auth/login",
        json={"email": "owner@example.com", "password": PASSWORD},
    )
    assert login.status_code == 200
    forgot = api_client.post(
        "/v1/auth/forgot-password", json={"email": "owner@example.com"}
    )
    assert forgot.status_code == 202
    token = _reset_token(api_client, "owner@example.com")
    new_password = "new-correct-horse-battery-staple"
    reset = api_client.post(
        "/v1/auth/reset-password",
        json={"token": token, "password": new_password},
    )
    assert reset.status_code == 200, reset.text

    app = cast(FastAPI, api_client.app)
    with Session(app.state.database.engine) as session:
        token_record = session.scalar(select(PasswordResetTokenRecord))
        auth_session = session.scalar(select(AuthSessionRecord))
        assert token_record is not None and token_record.used_at is not None
        assert auth_session is not None and auth_session.revoked_at is not None

    api_client.cookies.clear()
    assert api_client.post(
        "/v1/auth/login",
        json={"email": "owner@example.com", "password": PASSWORD},
    ).status_code == 401
    assert api_client.post(
        "/v1/auth/login",
        json={"email": "owner@example.com", "password": new_password},
    ).status_code == 200
    assert api_client.post(
        "/v1/auth/reset-password",
        json={"token": token, "password": "another-secure-password"},
    ).status_code == 400


def test_expired_password_reset_token_is_rejected(api_client: TestClient) -> None:
    _identity(api_client)
    api_client.post(
        "/v1/auth/forgot-password", json={"email": "owner@example.com"}
    )
    token = _reset_token(api_client, "owner@example.com")
    app = cast(FastAPI, api_client.app)
    with Session(app.state.database.engine) as session:
        record = session.scalar(select(PasswordResetTokenRecord))
        assert record is not None
        record.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()
    assert api_client.post(
        "/v1/auth/reset-password",
        json={"token": token, "password": "another-secure-password"},
    ).status_code == 400


def test_file_password_reset_mailer_writes_ignored_local_email(tmp_path) -> None:
    mailer = FilePasswordResetMailer(tmp_path / "mailbox")
    reset_url = "http://localhost:3000/reset-password?token=test-token"
    mailer.send(
        recipient="owner@example.com",
        display_name="Owner User",
        reset_url=reset_url,
    )
    messages = list((tmp_path / "mailbox").glob("password-reset-*.eml"))
    assert len(messages) == 1
    content = messages[0].read_text(encoding="utf-8")
    assert "To: owner@example.com" in content
    assert reset_url in content


def _email_verification_token(client: TestClient, index: int = -1) -> str:
    app = cast(FastAPI, client.app)
    mailer = cast(InMemoryEmailVerificationMailer, app.state.email_verification_mailer)
    values = parse_qs(urlparse(mailer.messages[index].verification_url).query)
    return values["token"][0]


def test_registration_requires_single_use_hashed_email_verification(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/v1/auth/register",
        json={
            "display_name": "Verification Owner",
            "email": "verify@example.com",
            "password": PASSWORD,
            "organization_name": "Verification Company",
            "organization_slug": "verification-company",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["user"]["email_verified"] is False
    token = _email_verification_token(api_client)

    app = cast(FastAPI, api_client.app)
    with Session(app.state.database.engine) as session:
        record = session.scalar(select(EmailVerificationTokenRecord))
        user = session.scalar(
            select(UserRecord).where(UserRecord.email == "verify@example.com")
        )
        assert record is not None
        assert record.token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert token != record.token_hash
        assert user is not None and user.email_verified_at is None

    verified = api_client.post("/v1/auth/verify-email", json={"token": token})
    assert verified.status_code == 200, verified.text
    assert api_client.get("/v1/auth/me").json()["email_verified"] is True
    assert api_client.post("/v1/auth/verify-email", json={"token": token}).status_code == 400


def test_resend_invalidates_previous_verification_token(api_client: TestClient) -> None:
    registration = api_client.post(
        "/v1/auth/register",
        json={
            "display_name": "Resend Owner",
            "email": "resend@example.com",
            "password": PASSWORD,
            "organization_name": "Resend Company",
            "organization_slug": "resend-company",
        },
    )
    assert registration.status_code == 201
    first_token = _email_verification_token(api_client)
    resent = api_client.post("/v1/auth/resend-verification", json={})
    assert resent.status_code == 202
    second_token = _email_verification_token(api_client)
    assert second_token != first_token
    assert api_client.post(
        "/v1/auth/verify-email", json={"token": first_token}
    ).status_code == 400
    assert api_client.post(
        "/v1/auth/verify-email", json={"token": second_token}
    ).status_code == 200

    message_count = len(
        cast(
            InMemoryEmailVerificationMailer,
            cast(FastAPI, api_client.app).state.email_verification_mailer,
        ).messages
    )
    same_response = api_client.post("/v1/auth/resend-verification", json={})
    assert same_response.status_code == 202
    assert len(
        cast(
            InMemoryEmailVerificationMailer,
            cast(FastAPI, api_client.app).state.email_verification_mailer,
        ).messages
    ) == message_count


def test_expired_email_verification_token_is_rejected(api_client: TestClient) -> None:
    response = api_client.post(
        "/v1/auth/register",
        json={
            "display_name": "Expired Owner",
            "email": "expired-verify@example.com",
            "password": PASSWORD,
            "organization_name": "Expired Verification",
            "organization_slug": "expired-verification",
        },
    )
    assert response.status_code == 201
    token = _email_verification_token(api_client)
    app = cast(FastAPI, api_client.app)
    with Session(app.state.database.engine) as session:
        record = session.scalar(select(EmailVerificationTokenRecord))
        assert record is not None
        record.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()
    assert api_client.post(
        "/v1/auth/verify-email", json={"token": token}
    ).status_code == 400


def test_file_email_verification_mailer_writes_ignored_local_email(tmp_path) -> None:
    mailer = FileEmailVerificationMailer(tmp_path / "mailbox")
    verification_url = "http://localhost:3000/verify-email?token=test-token"
    mailer.send(
        recipient="owner@example.com",
        display_name="Owner User",
        verification_url=verification_url,
    )
    messages = list((tmp_path / "mailbox").glob("email-verification-*.eml"))
    assert len(messages) == 1
    content = messages[0].read_text(encoding="utf-8")
    assert "To: owner@example.com" in content
    parsed = Parser(policy=policy.default).parsestr(content)
    body = parsed.get_body(preferencelist=("plain",))
    assert body is not None
    assert verification_url in body.get_content()

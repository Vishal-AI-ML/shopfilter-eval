from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.api.shopfilter_api.auth import MembershipRole, hash_password
from services.api.shopfilter_api.models import (
    AuthSessionRecord,
    MembershipRecord,
    Organization,
    UserRecord,
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

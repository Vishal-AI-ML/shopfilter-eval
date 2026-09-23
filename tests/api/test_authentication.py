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

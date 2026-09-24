from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import cast
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.shopfilter_api.auth import MembershipRole, hash_password
from services.api.shopfilter_api.invitation_mailer import InMemoryInvitationMailer
from services.api.shopfilter_api.models import (
    MembershipRecord,
    OrganizationInvitationRecord,
    UserRecord,
)

PASSWORD = "invitation-test-password"


def _organization(client: TestClient, suffix: str) -> tuple[str, dict[str, str]]:
    response = client.post(
        "/v1/organizations",
        json={"name": f"Invitation {suffix}", "slug": f"invitation-{suffix}"},
    )
    assert response.status_code == 201, response.text
    organization_id = response.json()["id"]
    return organization_id, {"X-Organization-ID": organization_id}


def _token(client: TestClient, index: int = -1) -> str:
    app = cast(FastAPI, client.app)
    mailer = cast(InMemoryInvitationMailer, app.state.invitation_mailer)
    return parse_qs(urlparse(mailer.messages[index].invitation_url).query)["token"][0]


def test_invitation_is_hash_only_and_acceptance_creates_verified_member(
    authenticated_client: TestClient,
) -> None:
    organization_id, headers = _organization(authenticated_client, "accept")
    invited = authenticated_client.post(
        "/v1/organization-invitations",
        headers=headers,
        json={"email": " NEW.MEMBER@EXAMPLE.COM ", "role": "ENGINEER"},
    )
    assert invited.status_code == 201, invited.text
    assert invited.json()["email"] == "new.member@example.com"
    assert "token" not in invited.text.casefold()
    token = _token(authenticated_client)

    app = cast(FastAPI, authenticated_client.app)
    with Session(app.state.database.engine) as session:
        record = session.scalar(select(OrganizationInvitationRecord))
        assert record is not None
        assert record.token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert token != record.token_hash

    accepted = authenticated_client.post(
        "/v1/auth/accept-invitation",
        json={
            "token": token,
            "display_name": " New Member ",
            "password": PASSWORD,
        },
    )
    assert accepted.status_code == 200, accepted.text
    user = accepted.json()["user"]
    assert user["email"] == "new.member@example.com"
    assert user["email_verified"] is True
    assert user["memberships"] == [
        {"organization_id": organization_id, "role": "ENGINEER"}
    ]
    assert authenticated_client.post(
        "/v1/auth/accept-invitation",
        json={"token": token, "display_name": "Replay", "password": PASSWORD},
    ).status_code == 400


def test_reinviting_same_email_invalidates_previous_link(
    authenticated_client: TestClient,
) -> None:
    _organization_id, headers = _organization(authenticated_client, "replace")
    body = {"email": "replace@example.com", "role": "VIEWER"}
    assert authenticated_client.post(
        "/v1/organization-invitations", headers=headers, json=body
    ).status_code == 201
    first = _token(authenticated_client)
    assert authenticated_client.post(
        "/v1/organization-invitations", headers=headers, json=body
    ).status_code == 201
    second = _token(authenticated_client)
    assert first != second
    assert authenticated_client.post(
        "/v1/auth/accept-invitation",
        json={"token": first, "display_name": "Replace", "password": PASSWORD},
    ).status_code == 400
    assert authenticated_client.post(
        "/v1/auth/accept-invitation",
        json={"token": second, "display_name": "Replace", "password": PASSWORD},
    ).status_code == 200


def test_existing_user_must_confirm_password_to_accept(
    authenticated_client: TestClient,
) -> None:
    organization_id, headers = _organization(authenticated_client, "existing")
    app = cast(FastAPI, authenticated_client.app)
    with Session(app.state.database.engine) as session:
        session.add(
            UserRecord(
                email="existing-invite@example.com",
                display_name="Existing User",
                password_hash=hash_password(PASSWORD),
                is_active=True,
                email_verified_at=None,
            )
        )
        session.commit()
    assert authenticated_client.post(
        "/v1/organization-invitations",
        headers=headers,
        json={"email": "existing-invite@example.com", "role": "REVIEWER"},
    ).status_code == 201
    token = _token(authenticated_client)
    assert authenticated_client.post(
        "/v1/auth/accept-invitation",
        json={"token": token, "password": "wrong-password-value"},
    ).status_code == 400
    accepted = authenticated_client.post(
        "/v1/auth/accept-invitation",
        json={"token": token, "password": PASSWORD},
    )
    assert accepted.status_code == 200
    assert accepted.json()["user"]["email_verified"] is True
    assert accepted.json()["user"]["memberships"] == [
        {"organization_id": organization_id, "role": "REVIEWER"}
    ]


def test_expired_and_revoked_invitations_cannot_be_accepted(
    authenticated_client: TestClient,
) -> None:
    _organization_id, headers = _organization(authenticated_client, "invalid")
    created = authenticated_client.post(
        "/v1/organization-invitations",
        headers=headers,
        json={"email": "expired-invite@example.com", "role": "VIEWER"},
    )
    token = _token(authenticated_client)
    app = cast(FastAPI, authenticated_client.app)
    with Session(app.state.database.engine) as session:
        record = session.get(OrganizationInvitationRecord, uuid.UUID(created.json()["id"]))
        assert record is not None
        record.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()
    assert authenticated_client.post(
        "/v1/auth/accept-invitation",
        json={"token": token, "display_name": "Expired", "password": PASSWORD},
    ).status_code == 400

    active = authenticated_client.post(
        "/v1/organization-invitations",
        headers=headers,
        json={"email": "revoked-invite@example.com", "role": "VIEWER"},
    )
    revoked_token = _token(authenticated_client)
    assert authenticated_client.delete(
        f"/v1/organization-invitations/{active.json()['id']}", headers=headers
    ).status_code == 204
    assert authenticated_client.post(
        "/v1/auth/accept-invitation",
        json={"token": revoked_token, "display_name": "Revoked", "password": PASSWORD},
    ).status_code == 400


def test_admin_cannot_invite_or_revoke_owner(authenticated_client: TestClient) -> None:
    organization_id, headers = _organization(authenticated_client, "admin-policy")
    owner_invite = authenticated_client.post(
        "/v1/organization-invitations",
        headers=headers,
        json={"email": "owner-invite@example.com", "role": "OWNER"},
    )
    assert owner_invite.status_code == 201
    app = cast(FastAPI, authenticated_client.app)
    with Session(app.state.database.engine) as session:
        admin = UserRecord(
            email="inviting-admin@example.com",
            display_name="Inviting Admin",
            password_hash=hash_password(PASSWORD),
            is_active=True,
            email_verified_at=datetime.now(UTC),
        )
        session.add(admin)
        session.flush()
        session.add(
            MembershipRecord(
                organization_id=uuid.UUID(organization_id),
                user_id=admin.id,
                role=MembershipRole.ADMIN.value,
            )
        )
        session.commit()
    login = authenticated_client.post(
        "/v1/auth/login",
        json={"email": "inviting-admin@example.com", "password": PASSWORD},
    )
    assert login.status_code == 200
    assert authenticated_client.post(
        "/v1/organization-invitations",
        headers=headers,
        json={"email": "another-owner@example.com", "role": "OWNER"},
    ).status_code == 403
    assert authenticated_client.delete(
        f"/v1/organization-invitations/{owner_invite.json()['id']}", headers=headers
    ).status_code == 403

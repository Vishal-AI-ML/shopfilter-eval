from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.shopfilter_api.auth import MembershipRole, hash_password
from services.api.shopfilter_api.models import MembershipRecord, UserRecord

TEST_USER_EMAIL = "api-owner@example.com"
TEST_USER_PASSWORD = "test-owner-password-123"

PASSWORD = "membership-test-password"


def _create_organization(client: TestClient, suffix: str) -> dict[str, str]:
    response = client.post(
        "/v1/organizations",
        json={"name": f"Governance {suffix}", "slug": f"governance-{suffix}"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_user(client: TestClient, email: str, *, active: bool = True) -> UserRecord:
    with Session(client.app.state.database.engine) as session:
        user = UserRecord(
            email=email,
            display_name=email.split("@", maxsplit=1)[0].title(),
            password_hash=hash_password(PASSWORD),
            is_active=active,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        session.expunge(user)
        return user


def _login(client: TestClient, email: str, password: str = PASSWORD) -> None:
    response = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text


def test_owner_and_admin_membership_governance(
    authenticated_client: TestClient,
) -> None:
    organization = _create_organization(authenticated_client, "roles")
    headers = {"X-Organization-ID": organization["id"]}
    _create_user(authenticated_client, "admin-governance@example.com")
    _create_user(authenticated_client, "engineer-governance@example.com")

    admin_add = authenticated_client.post(
        "/v1/organization-members",
        headers=headers,
        json={"email": " ADMIN-GOVERNANCE@EXAMPLE.COM ", "role": "ADMIN"},
    )
    assert admin_add.status_code == 201, admin_add.text
    assert set(admin_add.json()) == {
        "id",
        "organization_id",
        "user_id",
        "email",
        "display_name",
        "role",
        "created_at",
    }

    _login(authenticated_client, "admin-governance@example.com")
    engineer_add = authenticated_client.post(
        "/v1/organization-members",
        headers=headers,
        json={"email": "engineer-governance@example.com", "role": "ENGINEER"},
    )
    assert engineer_add.status_code == 201
    members = authenticated_client.get("/v1/organization-members", headers=headers)
    assert members.status_code == 200
    owner = next(member for member in members.json() if member["role"] == "OWNER")

    assert authenticated_client.patch(
        f"/v1/organization-members/{owner['id']}",
        headers=headers,
        json={"role": "VIEWER"},
    ).status_code == 403
    assert authenticated_client.delete(
        f"/v1/organization-members/{owner['id']}", headers=headers
    ).status_code == 403
    assert authenticated_client.patch(
        f"/v1/organization-members/{engineer_add.json()['id']}",
        headers=headers,
        json={"role": "OWNER"},
    ).status_code == 403



@pytest.mark.parametrize(
    "role",
    [MembershipRole.ENGINEER, MembershipRole.REVIEWER, MembershipRole.VIEWER],
)
def test_non_governance_roles_cannot_manage_memberships(
    authenticated_client: TestClient, role: MembershipRole
) -> None:
    organization = _create_organization(
        authenticated_client, f"deny-{role.value.casefold()}"
    )
    headers = {"X-Organization-ID": organization["id"]}
    email = f"membership-denied-{role.value.casefold()}@example.com"
    user = _create_user(authenticated_client, email)
    with Session(authenticated_client.app.state.database.engine) as session:
        session.add(
            MembershipRecord(
                organization_id=uuid.UUID(organization["id"]),
                user_id=user.id,
                role=role.value,
            )
        )
        session.commit()
    _login(authenticated_client, email)
    denied = authenticated_client.get("/v1/organization-members", headers=headers)
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Insufficient role for membership management"

def test_last_owner_cannot_be_demoted_or_removed(
    authenticated_client: TestClient,
) -> None:
    organization = _create_organization(authenticated_client, "last-owner")
    headers = {"X-Organization-ID": organization["id"]}
    membership = authenticated_client.get(
        "/v1/organization-members", headers=headers
    ).json()[0]

    demote = authenticated_client.patch(
        f"/v1/organization-members/{membership['id']}",
        headers=headers,
        json={"role": "ADMIN"},
    )
    remove = authenticated_client.delete(
        f"/v1/organization-members/{membership['id']}", headers=headers
    )
    assert demote.status_code == 409
    assert remove.status_code == 409
    assert demote.json()["detail"] == "Organization must retain at least one Owner"


def test_owner_transfer_allows_self_demote_when_another_owner_exists(
    authenticated_client: TestClient,
) -> None:
    organization = _create_organization(authenticated_client, "transfer")
    headers = {"X-Organization-ID": organization["id"]}
    _create_user(authenticated_client, "second-owner@example.com")
    second = authenticated_client.post(
        "/v1/organization-members",
        headers=headers,
        json={"email": "second-owner@example.com", "role": "OWNER"},
    )
    assert second.status_code == 201
    members = authenticated_client.get("/v1/organization-members", headers=headers).json()
    current = next(member for member in members if member["email"] == TEST_USER_EMAIL)
    demote = authenticated_client.patch(
        f"/v1/organization-members/{current['id']}",
        headers=headers,
        json={"role": "VIEWER"},
    )
    assert demote.status_code == 200
    assert demote.json()["role"] == "VIEWER"


def test_add_member_uses_safe_failure_and_cross_tenant_targets_are_hidden(
    authenticated_client: TestClient,
) -> None:
    first = _create_organization(authenticated_client, "safe-first")
    second = _create_organization(authenticated_client, "safe-second")
    first_headers = {"X-Organization-ID": first["id"]}
    second_headers = {"X-Organization-ID": second["id"]}
    _create_user(authenticated_client, "inactive-governance@example.com", active=False)

    missing = authenticated_client.post(
        "/v1/organization-members",
        headers=first_headers,
        json={"email": "missing-governance@example.com", "role": "VIEWER"},
    )
    inactive = authenticated_client.post(
        "/v1/organization-members",
        headers=first_headers,
        json={"email": "inactive-governance@example.com", "role": "VIEWER"},
    )
    assert missing.status_code == inactive.status_code == 404
    assert missing.json() == inactive.json() == {"detail": "Unable to add membership"}

    second_owner = authenticated_client.get(
        "/v1/organization-members", headers=second_headers
    ).json()[0]
    hidden = authenticated_client.patch(
        f"/v1/organization-members/{second_owner['id']}",
        headers=first_headers,
        json={"role": "ADMIN"},
    )
    assert hidden.status_code == 404
    with Session(authenticated_client.app.state.database.engine) as session:
        record = session.scalar(
            select(MembershipRecord).where(
                MembershipRecord.id == uuid.UUID(second_owner["id"])
            )
        )
        assert record is not None and record.role == MembershipRole.OWNER.value

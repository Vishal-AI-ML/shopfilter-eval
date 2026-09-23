from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.shopfilter_api.auth import MembershipRole, hash_password
from services.api.shopfilter_api.models import (
    MembershipRecord,
    Organization,
    UserRecord,
)

ROLE_PASSWORD = "role-test-password-123"


def _organization(client: TestClient, suffix: str) -> dict[str, str]:
    response = client.post(
        "/v1/organizations",
        json={"name": f"Organization {suffix}", "slug": f"organization-{suffix}"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _add_role_user(
    client: TestClient,
    *,
    organization_id: str,
    role: MembershipRole,
    suffix: str,
) -> None:
    with Session(client.app.state.database.engine) as session:
        user = UserRecord(
            email=f"{suffix}@example.com",
            display_name=f"{role.value} User",
            password_hash=hash_password(ROLE_PASSWORD),
            is_active=True,
        )
        session.add(user)
        session.flush()
        session.add(
            MembershipRecord(
                organization_id=uuid.UUID(organization_id),
                user_id=user.id,
                role=role.value,
            )
        )
        session.commit()
    login = client.post(
        "/v1/auth/login",
        json={"email": f"{suffix}@example.com", "password": ROLE_PASSWORD},
    )
    assert login.status_code == 200


def test_organization_creation_requires_authentication(api_client: TestClient) -> None:
    response = api_client.post(
        "/v1/organizations",
        json={"name": "Unauthorized", "slug": "unauthorized"},
    )
    assert response.status_code == 401


def test_organization_creator_becomes_owner(
    authenticated_client: TestClient,
) -> None:
    organization = _organization(authenticated_client, "owner")
    me = authenticated_client.get("/v1/auth/me").json()
    assert {
        "organization_id": organization["id"],
        "role": MembershipRole.OWNER.value,
    } in me["memberships"]


def test_forged_organization_header_is_hidden_from_non_member(
    authenticated_client: TestClient,
) -> None:
    organization = _organization(authenticated_client, "private")
    with Session(authenticated_client.app.state.database.engine) as session:
        outsider = UserRecord(
            email="outsider@example.com",
            display_name="Outsider",
            password_hash=hash_password(ROLE_PASSWORD),
            is_active=True,
        )
        session.add(outsider)
        session.commit()
    login = authenticated_client.post(
        "/v1/auth/login",
        json={"email": "outsider@example.com", "password": ROLE_PASSWORD},
    )
    assert login.status_code == 200
    response = authenticated_client.get(
        "/v1/projects",
        headers={"X-Organization-ID": organization["id"]},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Organization not found"


def test_viewer_and_reviewer_are_read_only_but_engineer_can_write(
    authenticated_client: TestClient,
) -> None:
    organization = _organization(authenticated_client, "roles")
    headers = {"X-Organization-ID": organization["id"]}
    owner_project = authenticated_client.post(
        "/v1/projects",
        headers=headers,
        json={"name": "Owner Project", "slug": "owner-project"},
    )
    assert owner_project.status_code == 201

    for role in (MembershipRole.VIEWER, MembershipRole.REVIEWER):
        suffix = role.value.casefold()
        _add_role_user(
            authenticated_client,
            organization_id=organization["id"],
            role=role,
            suffix=suffix,
        )
        assert authenticated_client.get("/v1/projects", headers=headers).status_code == 200
        denied = authenticated_client.post(
            "/v1/projects",
            headers=headers,
            json={"name": role.value, "slug": suffix},
        )
        assert denied.status_code == 403
        assert denied.json()["detail"] == "Insufficient role for this operation"

    _add_role_user(
        authenticated_client,
        organization_id=organization["id"],
        role=MembershipRole.ENGINEER,
        suffix="engineer",
    )
    allowed = authenticated_client.post(
        "/v1/projects",
        headers=headers,
        json={"name": "Engineer Project", "slug": "engineer-project"},
    )
    assert allowed.status_code == 201

    _add_role_user(
        authenticated_client,
        organization_id=organization["id"],
        role=MembershipRole.ADMIN,
        suffix="admin",
    )
    admin_allowed = authenticated_client.post(
        "/v1/projects",
        headers=headers,
        json={"name": "Admin Project", "slug": "admin-project"},
    )
    assert admin_allowed.status_code == 201


def test_member_cannot_read_another_organization_by_slug(
    authenticated_client: TestClient,
) -> None:
    organization = _organization(authenticated_client, "hidden")
    with Session(authenticated_client.app.state.database.engine) as session:
        outsider = UserRecord(
            email="slug-outsider@example.com",
            display_name="Slug Outsider",
            password_hash=hash_password(ROLE_PASSWORD),
            is_active=True,
        )
        session.add(outsider)
        session.commit()
        assert session.scalar(
            select(Organization).where(Organization.id == uuid.UUID(organization["id"]))
        ) is not None
    authenticated_client.post(
        "/v1/auth/login",
        json={"email": "slug-outsider@example.com", "password": ROLE_PASSWORD},
    )
    response = authenticated_client.get("/v1/organizations/organization-hidden")
    assert response.status_code == 404

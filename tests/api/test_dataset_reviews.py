from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from services.api.shopfilter_api.auth import MembershipRole, hash_password
from services.api.shopfilter_api.models import (
    DatasetVersionRecord,
    MembershipRecord,
    UserRecord,
)

PASSWORD = "review-role-password-123"


def _setup_dataset(client: TestClient) -> tuple[dict[str, str], dict[str, str], str]:
    organization = client.post(
        "/v1/organizations",
        json={"name": "Review Organization", "slug": "review-organization"},
    ).json()
    headers = {"X-Organization-ID": organization["id"]}
    project = client.post(
        "/v1/projects",
        headers=headers,
        json={"name": "Review Project", "slug": "review-project"},
    ).json()
    dataset = client.post(
        "/v1/datasets",
        headers=headers,
        json={"name": "Review Dataset", "project_id": project["id"]},
    ).json()
    with Session(client.app.state.database.engine) as session:
        version = DatasetVersionRecord(
            organization_id=uuid.UUID(organization["id"]),
            dataset_id=uuid.UUID(dataset["id"]),
            version="v1",
            status="PUBLISHED",
            content_hash="a" * 64,
            artifact_hash="b" * 64,
            item_count=1,
            provenance={"review_status": "SOURCE_VALIDATED", "human_reviewed": False},
        )
        session.add(version)
        session.commit()
        version_id = str(version.id)
    return organization, dataset, version_id


def _add_role_user(
    client: TestClient, organization_id: str, role: MembershipRole
) -> str:
    email = f"review-{role.value.casefold()}@example.com"
    with Session(client.app.state.database.engine) as session:
        user = UserRecord(
            email=email,
            display_name=f"{role.value.title()} User",
            password_hash=hash_password(PASSWORD),
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
    return email


def _login(client: TestClient, email: str) -> None:
    response = client.post(
        "/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200


def test_reviewer_can_append_human_review_without_mutating_source_provenance(
    authenticated_client: TestClient,
) -> None:
    organization, dataset, version_id = _setup_dataset(authenticated_client)
    headers = {"X-Organization-ID": organization["id"]}
    reviewer_email = _add_role_user(
        authenticated_client, organization["id"], MembershipRole.REVIEWER
    )
    _login(authenticated_client, reviewer_email)

    review = authenticated_client.post(
        f"/v1/datasets/{dataset['id']}/versions/{version_id}/reviews",
        headers=headers,
        json={"decision": "APPROVED", "note": "  Checked query relevance.  "},
    )
    assert review.status_code == 201, review.text
    assert review.json()["decision"] == "APPROVED"
    assert review.json()["note"] == "Checked query relevance."
    assert review.json()["reviewer_display_name"] == "Reviewer User"

    listed = authenticated_client.get(
        f"/v1/datasets/{dataset['id']}/versions/{version_id}/reviews",
        headers=headers,
    )
    assert listed.status_code == 200
    assert listed.json() == [review.json()]
    version = authenticated_client.get(
        f"/v1/datasets/{dataset['id']}/versions/{version_id}", headers=headers
    ).json()
    assert version["provenance"] == {
        "review_status": "SOURCE_VALIDATED",
        "human_reviewed": False,
    }
    assert authenticated_client.post(
        "/v1/catalogs",
        headers=headers,
        json={"name": "Denied Catalog", "project_id": dataset["project_id"]},
    ).status_code == 403
    assert authenticated_client.get(
        "/v1/organization-members", headers=headers
    ).status_code == 403


@pytest.mark.parametrize("role", [MembershipRole.ENGINEER, MembershipRole.VIEWER])
def test_engineer_and_viewer_cannot_submit_dataset_reviews(
    authenticated_client: TestClient, role: MembershipRole
) -> None:
    organization, dataset, version_id = _setup_dataset(authenticated_client)
    headers = {"X-Organization-ID": organization["id"]}
    email = _add_role_user(authenticated_client, organization["id"], role)
    _login(authenticated_client, email)
    denied = authenticated_client.post(
        f"/v1/datasets/{dataset['id']}/versions/{version_id}/reviews",
        headers=headers,
        json={"decision": "REJECTED", "note": "Not permitted"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Insufficient role for dataset review"


def test_cross_tenant_review_target_is_hidden(
    authenticated_client: TestClient,
) -> None:
    _first_org, first_dataset, first_version = _setup_dataset(authenticated_client)
    second_org = authenticated_client.post(
        "/v1/organizations",
        json={"name": "Second Review Org", "slug": "second-review-org"},
    ).json()
    response = authenticated_client.post(
        f"/v1/datasets/{first_dataset['id']}/versions/{first_version}/reviews",
        headers={"X-Organization-ID": second_org["id"]},
        json={"decision": "APPROVED"},
    )
    assert response.status_code == 404


def test_owner_and_admin_can_submit_append_only_review_decisions(
    authenticated_client: TestClient,
) -> None:
    organization, dataset, version_id = _setup_dataset(authenticated_client)
    headers = {"X-Organization-ID": organization["id"]}
    path = f"/v1/datasets/{dataset['id']}/versions/{version_id}/reviews"
    owner_review = authenticated_client.post(
        path, headers=headers, json={"decision": "APPROVED", "note": "Owner check"}
    )
    assert owner_review.status_code == 201

    admin_email = _add_role_user(
        authenticated_client, organization["id"], MembershipRole.ADMIN
    )
    _login(authenticated_client, admin_email)
    admin_review = authenticated_client.post(
        path, headers=headers, json={"decision": "REJECTED", "note": "Admin check"}
    )
    assert admin_review.status_code == 201
    reviews = authenticated_client.get(path, headers=headers)
    assert reviews.status_code == 200
    assert len(reviews.json()) == 2
    assert {review["decision"] for review in reviews.json()} == {
        "APPROVED",
        "REJECTED",
    }

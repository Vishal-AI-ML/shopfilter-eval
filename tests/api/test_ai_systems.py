from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from services.api.shopfilter_api.auth import MembershipRole, hash_password
from services.api.shopfilter_api.models import MembershipRecord, UserRecord

ROLE_PASSWORD = "ai-system-role-password-123"


def _organization_and_project(client: TestClient, suffix: str) -> tuple[dict, dict, dict]:
    organization_response = client.post(
        "/v1/organizations",
        json={"name": f"Organization {suffix}", "slug": f"organization-{suffix}"},
    )
    assert organization_response.status_code == 201
    organization = organization_response.json()
    headers = {"X-Organization-ID": organization["id"]}
    project_response = client.post(
        "/v1/projects",
        headers=headers,
        json={"name": f"Project {suffix}", "slug": f"project-{suffix}"},
    )
    assert project_response.status_code == 201
    return organization, project_response.json(), headers


def test_rag_ai_system_is_project_scoped_and_versioned_immutably(
    authenticated_client: TestClient,
) -> None:
    _, first_project, first_headers = _organization_and_project(
        authenticated_client, "first"
    )
    _, second_project, second_headers = _organization_and_project(
        authenticated_client, "second"
    )
    created = authenticated_client.post(
        "/v1/ai-systems",
        headers=first_headers,
        json={
            "project_id": first_project["id"],
            "name": "Shopping Assistant",
            "system_type": "RAG_ASSISTANT",
            "provider": "disabled",
            "description": "Grounded reference assistant",
        },
    )
    assert created.status_code == 201, created.text
    system = created.json()
    assert system["system_type"] == "RAG_ASSISTANT"
    assert system["status"] == "ACTIVE"

    version_response = authenticated_client.post(
        f"/v1/ai-systems/{system['id']}/versions",
        headers=first_headers,
        json={
            "version": "v1",
            "configuration": {"top_k": 10, "prompt_version": "prompt-v1"},
            "capabilities": {
                "semantic_retrieval": True,
                "hybrid_retrieval": True,
                "generation": True,
                "citations": True,
                "traces": True,
            },
        },
    )
    assert version_response.status_code == 201, version_response.text
    version = version_response.json()
    assert version["ai_system_id"] == system["id"]
    assert version["capabilities"]["citations"] is True
    assert version["status"] == "PUBLISHED"
    assert len(version["content_hash"]) == 64

    filtered = authenticated_client.get(
        "/v1/ai-systems",
        headers=first_headers,
        params={"project_id": first_project["id"]},
    )
    assert [item["id"] for item in filtered.json()] == [system["id"]]
    assert authenticated_client.get(
        "/v1/ai-systems",
        headers=first_headers,
        params={"project_id": second_project["id"]},
    ).json() == []
    assert authenticated_client.get(
        "/v1/ai-systems", headers=second_headers
    ).json() == []


def test_legacy_and_ai_routes_share_persisted_identifiers(
    authenticated_client: TestClient,
) -> None:
    _, project, headers = _organization_and_project(authenticated_client, "compat")
    legacy = authenticated_client.post(
        "/v1/search-systems",
        headers=headers,
        json={"project_id": project["id"], "name": "Legacy", "provider": "demo"},
    )
    assert legacy.status_code == 201
    system_id = legacy.json()["id"]
    ai_systems = authenticated_client.get("/v1/ai-systems", headers=headers).json()
    assert ai_systems[0]["id"] == system_id
    assert ai_systems[0]["system_type"] == "LEXICAL_SEARCH"

    legacy_version = authenticated_client.post(
        f"/v1/search-systems/{system_id}/versions",
        headers=headers,
        json={"version": "v1", "configuration": {"top_k": 10}},
    )
    assert legacy_version.status_code == 201
    ai_versions = authenticated_client.get(
        f"/v1/ai-systems/{system_id}/versions", headers=headers
    ).json()
    assert ai_versions[0]["id"] == legacy_version.json()["id"]
    assert ai_versions[0]["capabilities"]["lexical_retrieval"] is True


def test_reviewer_cannot_create_ai_system(authenticated_client: TestClient) -> None:
    organization, project, headers = _organization_and_project(
        authenticated_client, "reviewer"
    )
    with Session(authenticated_client.app.state.database.engine) as session:
        reviewer = UserRecord(
            email="ai-reviewer@example.com",
            display_name="AI Reviewer",
            password_hash=hash_password(ROLE_PASSWORD),
            is_active=True,
        )
        session.add(reviewer)
        session.flush()
        session.add(
            MembershipRecord(
                organization_id=uuid.UUID(organization["id"]),
                user_id=reviewer.id,
                role=MembershipRole.REVIEWER.value,
            )
        )
        session.commit()
    login = authenticated_client.post(
        "/v1/auth/login",
        json={"email": "ai-reviewer@example.com", "password": ROLE_PASSWORD},
    )
    assert login.status_code == 200
    denied = authenticated_client.post(
        "/v1/ai-systems",
        headers=headers,
        json={
            "project_id": project["id"],
            "name": "Denied",
            "system_type": "RAG_ASSISTANT",
            "provider": "disabled",
        },
    )
    assert denied.status_code == 403
    assert authenticated_client.get("/v1/ai-systems", headers=headers).status_code == 200

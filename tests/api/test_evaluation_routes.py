from __future__ import annotations

from fastapi.testclient import TestClient


def _organization(client: TestClient, name: str, slug: str) -> dict[str, str]:
    response = client.post("/v1/organizations", json={"name": name, "slug": slug})
    assert response.status_code == 201
    return response.json()


def test_search_system_routes_are_tenant_scoped(authenticated_client: TestClient) -> None:
    first = _organization(authenticated_client, "First", "first")
    second = _organization(authenticated_client, "Second", "second")
    first_headers = {"X-Organization-ID": first["id"]}
    second_headers = {"X-Organization-ID": second["id"]}
    project = authenticated_client.post(
        "/v1/projects",
        headers=first_headers,
        json={"name": "Search", "slug": "search"},
    ).json()
    system_response = authenticated_client.post(
        "/v1/search-systems",
        headers=first_headers,
        json={"project_id": project["id"], "name": "Demo", "provider": "demo"},
    )
    assert system_response.status_code == 201
    system = system_response.json()
    version_response = authenticated_client.post(
        f"/v1/search-systems/{system['id']}/versions",
        headers=first_headers,
        json={"version": "v1", "configuration": {"top_k": 10}},
    )
    assert version_response.status_code == 201
    assert len(authenticated_client.get("/v1/search-systems", headers=first_headers).json()) == 1
    assert authenticated_client.get("/v1/search-systems", headers=second_headers).json() == []
    hidden_versions = authenticated_client.get(
        f"/v1/search-systems/{system['id']}/versions", headers=second_headers
    )
    assert hidden_versions.json() == []
    cross_tenant_create = authenticated_client.post(
        f"/v1/search-systems/{system['id']}/versions",
        headers=second_headers,
        json={"version": "stolen", "configuration": {}},
    )
    assert cross_tenant_create.status_code == 404

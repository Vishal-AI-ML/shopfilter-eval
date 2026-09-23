
from __future__ import annotations

from fastapi.testclient import TestClient


def _organization(client: TestClient, name: str, slug: str) -> dict[str, str]:
    response = client.post("/v1/organizations", json={"name": name, "slug": slug})
    assert response.status_code == 201, response.text
    return response.json()


def _headers(organization_id: str) -> dict[str, str]:
    return {"X-Organization-ID": organization_id}


def test_tenant_header_is_required(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/v1/projects")
    assert response.status_code == 400
    assert response.json()["detail"] == "X-Organization-ID header is required"


def test_projects_catalogs_and_datasets_are_tenant_scoped(authenticated_client: TestClient) -> None:
    organization_a = _organization(authenticated_client, "Organization A", "organization-a")
    organization_b = _organization(authenticated_client, "Organization B", "organization-b")

    project_response = authenticated_client.post(
        "/v1/projects",
        headers=_headers(organization_a["id"]),
        json={"name": "Search Quality", "slug": "search-quality"},
    )
    assert project_response.status_code == 201, project_response.text
    project = project_response.json()

    catalog_response = authenticated_client.post(
        "/v1/catalogs",
        headers=_headers(organization_a["id"]),
        json={"project_id": project["id"], "name": "Primary Catalog"},
    )
    assert catalog_response.status_code == 201, catalog_response.text
    dataset_response = authenticated_client.post(
        "/v1/datasets",
        headers=_headers(organization_a["id"]),
        json={"project_id": project["id"], "name": "ESCI Golden"},
    )
    assert dataset_response.status_code == 201, dataset_response.text

    assert len(authenticated_client.get("/v1/projects", headers=_headers(organization_a["id"])).json()) == 1
    assert len(authenticated_client.get("/v1/catalogs", headers=_headers(organization_a["id"])).json()) == 1
    assert len(authenticated_client.get("/v1/datasets", headers=_headers(organization_a["id"])).json()) == 1
    assert authenticated_client.get("/v1/projects", headers=_headers(organization_b["id"])).json() == []
    assert authenticated_client.get("/v1/catalogs", headers=_headers(organization_b["id"])).json() == []
    assert authenticated_client.get("/v1/datasets", headers=_headers(organization_b["id"])).json() == []

    cross_tenant = authenticated_client.post(
        "/v1/catalogs",
        headers=_headers(organization_b["id"]),
        json={"project_id": project["id"], "name": "Stolen Catalog"},
    )
    assert cross_tenant.status_code == 404
    assert cross_tenant.json()["detail"] == "Project not found"


def test_duplicate_names_return_conflict(authenticated_client: TestClient) -> None:
    organization = _organization(authenticated_client, "Organization", "organization")
    body = {"name": "Search Quality", "slug": "search-quality"}
    first = authenticated_client.post("/v1/projects", headers=_headers(organization["id"]), json=body)
    second = authenticated_client.post("/v1/projects", headers=_headers(organization["id"]), json=body)
    assert first.status_code == 201
    assert second.status_code == 409

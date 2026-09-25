from __future__ import annotations

from fastapi.testclient import TestClient


def _scope(client: TestClient) -> tuple[dict[str, str], dict[str, str]]:
    organization_response = client.post(
        "/v1/organizations",
        json={"name": "Catalog Import", "slug": "catalog-import"},
    )
    assert organization_response.status_code == 201, organization_response.text
    organization = organization_response.json()
    headers = {"X-Organization-ID": organization["id"]}
    project_response = client.post(
        "/v1/projects",
        headers=headers,
        json={"name": "Catalog Project", "slug": "catalog-project"},
    )
    assert project_response.status_code == 201, project_response.text
    return headers, project_response.json()


def _artifact(title: str = "Black Running Shoe") -> dict[str, object]:
    return {
        "catalog_id": "browser-catalog",
        "version": "v1",
        "products": [
            {
                "product_id": "P-1",
                "title": title,
                "category": "shoes",
                "price": "1999",
                "currency": "INR",
            }
        ],
    }


def test_browser_catalog_import_is_validated_persisted_and_idempotent(
    authenticated_client: TestClient,
) -> None:
    headers, project = _scope(authenticated_client)
    body = {"project_id": project["id"], "artifact": _artifact()}

    created = authenticated_client.post(
        "/v1/catalog-imports", headers=headers, json=body
    )
    repeated = authenticated_client.post(
        "/v1/catalog-imports", headers=headers, json=body
    )

    assert created.status_code == repeated.status_code == 201
    assert created.json()["created"] is True
    assert repeated.json()["created"] is False
    assert created.json()["version_id"] == repeated.json()["version_id"]
    assert created.json()["item_count"] == 1
    assert len(created.json()["content_hash"]) == 64
    assert len(created.json()["artifact_hash"]) == 64

    catalogs = authenticated_client.get("/v1/catalogs", headers=headers)
    assert catalogs.status_code == 200
    catalog = next(item for item in catalogs.json() if item["external_id"] == "browser-catalog")
    versions = authenticated_client.get(
        f"/v1/catalogs/{catalog['id']}/versions", headers=headers
    )
    assert versions.status_code == 200
    assert versions.json()[0]["status"] == "PUBLISHED"
    assert versions.json()[0]["item_count"] == 1


def test_browser_catalog_import_rejects_invalid_and_mutated_immutable_content(
    authenticated_client: TestClient,
) -> None:
    headers, project = _scope(authenticated_client)

    invalid = authenticated_client.post(
        "/v1/catalog-imports",
        headers=headers,
        json={
            "project_id": project["id"],
            "artifact": {"catalog_id": "invalid", "version": "v1", "products": []},
        },
    )
    assert invalid.status_code == 409
    assert invalid.json() == {"detail": "Published catalog must contain at least one product"}

    first = authenticated_client.post(
        "/v1/catalog-imports",
        headers=headers,
        json={"project_id": project["id"], "artifact": _artifact()},
    )
    changed = authenticated_client.post(
        "/v1/catalog-imports",
        headers=headers,
        json={
            "project_id": project["id"],
            "artifact": _artifact("Changed immutable title"),
        },
    )
    assert first.status_code == 201
    assert changed.status_code == 409
    assert changed.json() == {
        "detail": "Published ID and version already exist with different immutable content"
    }


def test_browser_catalog_import_rejects_non_json_requests(
    authenticated_client: TestClient,
) -> None:
    headers, _project = _scope(authenticated_client)
    headers["Content-Type"] = "text/plain"
    response = authenticated_client.post(
        "/v1/catalog-imports",
        content=b"not-json",
        headers=headers,
    )
    assert response.status_code == 415
    assert response.json() == {"detail": "Catalog import requires JSON"}

from __future__ import annotations

from fastapi.testclient import TestClient


def _organization(client: TestClient, suffix: str) -> tuple[dict, dict[str, str]]:
    response = client.post(
        "/v1/organizations",
        json={"name": f"Assistant {suffix}", "slug": f"assistant-{suffix}"},
    )
    assert response.status_code == 201
    organization = response.json()
    return organization, {"X-Organization-ID": organization["id"]}


def test_playground_returns_grounded_catalog_evidence(
    authenticated_client: TestClient,
) -> None:
    _, headers = _organization(authenticated_client, "primary")
    project = authenticated_client.post(
        "/v1/projects",
        headers=headers,
        json={"name": "Shopping Assistant", "slug": "shopping-assistant"},
    ).json()
    catalog_import = authenticated_client.post(
        "/v1/catalog-imports",
        headers=headers,
        json={
            "project_id": project["id"],
            "artifact": {
                "catalog_id": "assistant-catalog",
                "version": "v1",
                "products": [
                    {
                        "product_id": "SHOE-1",
                        "title": "Black Road Running Shoe",
                        "description": "Lightweight daily running shoe",
                        "category": "shoes",
                        "subcategory": "running_shoes",
                        "color": "black",
                        "price": "2499",
                        "currency": "INR",
                        "availability": "in_stock",
                    },
                    {
                        "product_id": "SHOE-2",
                        "title": "Brown Hiking Boot",
                        "description": "Trail boot for hiking",
                        "category": "shoes",
                        "subcategory": "boots",
                        "color": "brown",
                        "price": "4999",
                        "currency": "INR",
                        "availability": "in_stock",
                    },
                ],
            },
        },
    )
    assert catalog_import.status_code == 201, catalog_import.text
    system = authenticated_client.post(
        "/v1/ai-systems",
        headers=headers,
        json={
            "project_id": project["id"],
            "name": "Reference Assistant",
            "system_type": "RAG_ASSISTANT",
            "provider": "deterministic-reference",
        },
    ).json()
    version = authenticated_client.post(
        f"/v1/ai-systems/{system['id']}/versions",
        headers=headers,
        json={
            "version": "reference-v1",
            "configuration": {"top_k": 5},
            "capabilities": {
                "query_understanding": True,
                "lexical_retrieval": True,
                "generation": False,
                "citations": True,
                "traces": True,
            },
        },
    ).json()

    response = authenticated_client.post(
        "/v1/assistant/playground",
        headers=headers,
        json={
            "project_id": project["id"],
            "catalog_version_id": catalog_import.json()["version_id"],
            "ai_system_version_id": version["id"],
            "query": "black running shoes under INR 3000 in stock",
            "top_k": 5,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "DETERMINISTIC_REFERENCE"
    assert body["generation_provider"] == "DISABLED"
    assert body["system"]["version"] == "reference-v1"
    assert body["catalog"]["version"] == "v1"
    assert [product["product_id"] for product in body["products"]] == ["SHOE-1"]
    assert body["products"][0]["price"] == "2499"
    assert body["citations"] == [
        {
            "claim": "Black Road Running Shoe is listed at INR 2499.",
            "source_id": "SHOE-1",
            "source_version": "v1",
        }
    ]
    assert "SHOE-1" in body["answer"]
    assert body["applied_filters"]["max_price"] == "3000"
    assert body["latency_ms"] >= 0


def test_playground_hides_cross_tenant_resources(
    authenticated_client: TestClient,
) -> None:
    _, first_headers = _organization(authenticated_client, "owner")
    _, second_headers = _organization(authenticated_client, "outsider")
    project = authenticated_client.post(
        "/v1/projects",
        headers=first_headers,
        json={"name": "Private Assistant", "slug": "private-assistant"},
    ).json()
    catalog = authenticated_client.post(
        "/v1/catalog-imports",
        headers=first_headers,
        json={
            "project_id": project["id"],
            "artifact": {
                "catalog_id": "private-catalog",
                "version": "v1",
                "products": [
                    {
                        "product_id": "P-1",
                        "title": "Private Product",
                        "category": "shoes",
                        "price": "100",
                        "currency": "INR",
                    }
                ],
            },
        },
    ).json()
    system = authenticated_client.post(
        "/v1/ai-systems",
        headers=first_headers,
        json={
            "project_id": project["id"],
            "name": "Private System",
            "system_type": "LEXICAL_SEARCH",
            "provider": "deterministic-reference",
        },
    ).json()
    version = authenticated_client.post(
        f"/v1/ai-systems/{system['id']}/versions",
        headers=first_headers,
        json={
            "version": "v1",
            "configuration": {},
            "capabilities": {"lexical_retrieval": True, "citations": True},
        },
    ).json()
    hidden = authenticated_client.post(
        "/v1/assistant/playground",
        headers=second_headers,
        json={
            "project_id": project["id"],
            "catalog_version_id": catalog["version_id"],
            "ai_system_version_id": version["id"],
            "query": "private product",
        },
    )
    assert hidden.status_code == 404

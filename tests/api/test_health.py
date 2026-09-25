
from fastapi.testclient import TestClient


def test_liveness_does_not_require_database_header(api_client: TestClient) -> None:
    response = api_client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_checks_database(api_client: TestClient) -> None:
    response = api_client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_openapi_exposes_core_resource_routes(api_client: TestClient) -> None:
    schema = api_client.get("/openapi.json").json()
    assert schema["info"]["title"] == "ShopFilter Eval API"
    assert "/v1/projects" in schema["paths"]
    assert "/v1/catalogs" in schema["paths"]
    assert "/v1/datasets" in schema["paths"]
    assert "/v1/search-systems" in schema["paths"]
    assert "/v1/ai-systems" in schema["paths"]
    assert "/v1/assistant/playground" in schema["paths"]
    assert "/v1/evaluation-runs" in schema["paths"]

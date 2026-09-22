from __future__ import annotations

from pathlib import Path

import pytest

from packages.demo_search.engine import DemoSearchEngine
from packages.evaluation_engine.catalog import load_catalog
from packages.evaluation_engine.models import SearchRequest, SearchResponse
from packages.evaluation_engine.search_execution import execute_search
from packages.search_adapters import (
    AdapterCapabilities,
    AdapterCapabilityLevel,
    AdapterErrorCode,
    DemoSearchAdapter,
    SearchAdapterError,
)

CATALOG_PATH = Path(__file__).parents[2] / "data" / "demo" / "catalog-v1.json"


class MockSearchAdapter:
    provider_name = "mock"
    capabilities = AdapterCapabilities(level=AdapterCapabilityLevel.BASIC)

    def __init__(self, response: SearchResponse) -> None:
        self.response = response
        self.calls: list[SearchRequest] = []

    async def search(self, request: SearchRequest) -> SearchResponse:
        self.calls.append(request)
        return self.response


class TimeoutBackend:
    def search(self, request: SearchRequest) -> SearchResponse:
        del request
        raise TimeoutError


class FailingBackend:
    def search(self, request: SearchRequest) -> SearchResponse:
        del request
        raise RuntimeError("internal provider details")


class InvalidProviderBackend:
    def __init__(self, response: SearchResponse) -> None:
        self.response = response

    def search(self, request: SearchRequest) -> SearchResponse:
        del request
        return self.response.model_copy(update={"provider": "unexpected-provider"})


def demo_response() -> SearchResponse:
    catalog = load_catalog(CATALOG_PATH)
    return DemoSearchEngine(catalog).search(SearchRequest(query="running shoes", top_k=3))


@pytest.mark.asyncio
async def test_execution_boundary_accepts_replaceable_mock_adapter() -> None:
    response = demo_response().model_copy(update={"provider": "mock"})
    adapter = MockSearchAdapter(response)
    request = SearchRequest(query="replacement adapter", top_k=2)

    result = await execute_search(adapter, request)

    assert result is response
    assert adapter.calls == [request]


@pytest.mark.asyncio
async def test_demo_adapter_normalizes_timeout() -> None:
    adapter = DemoSearchAdapter(TimeoutBackend())
    with pytest.raises(SearchAdapterError) as error:
        await adapter.search(SearchRequest(query="shoes"))
    assert error.value.code == AdapterErrorCode.TIMEOUT
    assert error.value.retryable is True
    assert error.value.provider == "shopfilter-demo"


@pytest.mark.asyncio
async def test_demo_adapter_normalizes_provider_failure() -> None:
    adapter = DemoSearchAdapter(FailingBackend())
    with pytest.raises(SearchAdapterError) as error:
        await adapter.search(SearchRequest(query="shoes"))
    assert error.value.code == AdapterErrorCode.PROVIDER_ERROR
    assert error.value.retryable is False
    assert "internal provider details" not in str(error.value)


@pytest.mark.asyncio
async def test_demo_adapter_rejects_mismatched_provider_identity() -> None:
    adapter = DemoSearchAdapter(InvalidProviderBackend(demo_response()))
    with pytest.raises(SearchAdapterError) as error:
        await adapter.search(SearchRequest(query="shoes"))
    assert error.value.code == AdapterErrorCode.INVALID_RESPONSE

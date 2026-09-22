from pathlib import Path

import pytest

from packages.demo_search.engine import DemoSearchEngine
from packages.evaluation_engine.catalog import load_catalog
from packages.evaluation_engine.models import SearchRequest
from packages.search_adapters import (
    AdapterCapabilityLevel,
    DemoSearchAdapter,
    SearchAdapter,
)

CATALOG_PATH = Path(__file__).parents[2] / "data" / "demo" / "catalog-v1.json"


def make_adapter() -> DemoSearchAdapter:
    catalog = load_catalog(CATALOG_PATH)
    return DemoSearchAdapter(DemoSearchEngine(catalog))


def test_demo_adapter_satisfies_runtime_protocol() -> None:
    assert isinstance(make_adapter(), SearchAdapter)


def test_demo_adapter_declares_trace_capabilities() -> None:
    capabilities = make_adapter().capabilities
    assert capabilities.level == AdapterCapabilityLevel.TRACE
    assert capabilities.interpreted_query is True
    assert capabilities.applied_filters is True
    assert capabilities.retrieval_candidates is True
    assert capabilities.filtered_candidates is True
    assert capabilities.scores is True


@pytest.mark.asyncio
async def test_demo_adapter_returns_normalized_response() -> None:
    adapter = make_adapter()
    response = await adapter.search(
        SearchRequest(query="nike black running shoes under 3000 size 9", top_k=5)
    )
    assert response.provider == adapter.provider_name
    assert response.system_version == "demo-v1"
    assert response.products
    assert response.interpreted_query is not None
    assert response.retrieved_candidates is not None
    assert response.filtered_candidates is not None

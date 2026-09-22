from pathlib import Path

import pytest

from packages.demo_search.engine import DemoSearchEngine, load_search_config
from packages.evaluation_engine.catalog import load_catalog
from packages.evaluation_engine.models import Catalog, SearchRequest

CATALOG_PATH = Path(__file__).parents[2] / "data" / "demo" / "catalog-v1.json"


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return load_catalog(CATALOG_PATH)


@pytest.fixture(scope="module")
def engine(catalog: Catalog) -> DemoSearchEngine:
    return DemoSearchEngine(catalog)


def test_known_query_satisfies_all_hard_filters(engine: DemoSearchEngine) -> None:
    response = engine.search(
        SearchRequest(query="nike men's black running shoes below ₹3000 size 9", top_k=10)
    )

    assert response.products
    for result in response.products:
        product = result.product
        assert product.brand == "Nike"
        assert product.gender == "men"
        assert product.color == "black"
        assert product.subcategory == "running_shoes"
        assert product.price <= 3000
        assert "9" in product.sizes


def test_results_are_ranked_from_one(engine: DemoSearchEngine) -> None:
    response = engine.search(SearchRequest(query="running shoes", top_k=5))
    assert [result.rank for result in response.products] == list(
        range(1, len(response.products) + 1)
    )
    assert [result.score for result in response.products] == sorted(
        [result.score for result in response.products], reverse=True
    )


def test_top_k_is_respected(engine: DemoSearchEngine) -> None:
    response = engine.search(SearchRequest(query="shoes", top_k=3))
    assert len(response.products) == 3


def test_price_filter_is_hard_constraint(engine: DemoSearchEngine) -> None:
    response = engine.search(SearchRequest(query="shoes under 2000", top_k=20))
    assert response.products
    assert all(result.product.price <= 2000 for result in response.products)


def test_availability_filter_is_applied(engine: DemoSearchEngine) -> None:
    response = engine.search(SearchRequest(query="available shoes", top_k=20))
    assert response.products
    assert all(result.product.availability.value == "in_stock" for result in response.products)


def test_unknown_lexical_query_returns_no_results(engine: DemoSearchEngine) -> None:
    response = engine.search(SearchRequest(query="xyzzy", top_k=10))
    assert response.products == []
    assert response.retrieved_candidates == []


def test_pipeline_trace_data_is_present(engine: DemoSearchEngine) -> None:
    response = engine.search(SearchRequest(query="black running shoes", top_k=10, seed=42))
    assert response.provider == "shopfilter-demo"
    assert response.system_version == "demo-v1"
    assert response.interpreted_query is not None
    assert response.applied_filters is not None
    assert response.retrieved_candidates is not None
    assert response.filtered_candidates is not None
    assert response.metadata["seed"] == 42
    assert response.metadata["pipeline_stages"] == [
        "query_understanding",
        "retrieval",
        "filtering",
        "ranking",
    ]


def test_same_request_has_deterministic_products_and_scores(engine: DemoSearchEngine) -> None:
    request = SearchRequest(query="running shoes", top_k=10, seed=7)
    first = engine.search(request)
    second = engine.search(request)
    assert [(item.product.product_id, item.score) for item in first.products] == [
        (item.product.product_id, item.score) for item in second.products
    ]


def test_retrieval_precedes_filtering(engine: DemoSearchEngine) -> None:
    response = engine.search(SearchRequest(query="nike running shoes", top_k=10))
    assert response.retrieved_candidates is not None
    assert response.filtered_candidates is not None
    assert len(response.retrieved_candidates) >= len(response.filtered_candidates)
    assert set(response.filtered_candidates).issubset(response.retrieved_candidates)


def test_search_weights_are_configuration_backed() -> None:
    config = load_search_config()
    assert config.field_weights["title"] > config.field_weights["description"]
    assert config.candidate_limit == 100

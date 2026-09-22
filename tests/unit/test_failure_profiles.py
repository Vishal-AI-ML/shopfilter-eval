from pathlib import Path

import pytest

from packages.demo_search.engine import DemoSearchEngine
from packages.evaluation_engine.catalog import load_catalog
from packages.evaluation_engine.datasets import GoldenCase, load_golden_dataset
from packages.evaluation_engine.failures import classify_case_failure
from packages.evaluation_engine.models import FailureType, SearchRequest, SearchResponse
from packages.search_adapters.demo import DemoSearchAdapter
from packages.search_adapters.faults import (
    FaultInjectingSearchAdapter,
    load_failure_profiles,
)

ROOT = Path(__file__).parents[2]
CATALOG_PATH = ROOT / "data" / "demo" / "catalog-v1.json"
DATASET_PATH = ROOT / "data" / "goldens" / "golden-v1.json"


def case_by_id(case_id: str) -> GoldenCase:
    dataset = load_golden_dataset(DATASET_PATH)
    return next(case for case in dataset.cases if case.case_id == case_id)


def adapter_for(profile_id: str) -> FaultInjectingSearchAdapter:
    catalog = load_catalog(CATALOG_PATH)
    base = DemoSearchAdapter(DemoSearchEngine(catalog))
    return FaultInjectingSearchAdapter(
        base,
        catalog,
        load_failure_profiles()[profile_id],
    )


async def response_for(
    profile_id: str,
    case_id: str,
) -> tuple[GoldenCase, SearchResponse]:
    case = case_by_id(case_id)
    response = await adapter_for(profile_id).search(
        SearchRequest(query=case.query, top_k=100)
    )
    return case, response


def test_all_versioned_failure_profiles_load() -> None:
    profiles = load_failure_profiles()
    assert set(profiles) == {
        "healthy-v1",
        "filter-broken-v1",
        "retrieval-broken-v1",
        "ranking-broken-v1",
        "query-parser-regression-v1",
        "latency-regression-v1",
    }


@pytest.mark.asyncio
async def test_healthy_profile_has_no_failure_for_known_good_case() -> None:
    case, response = await response_for("healthy-v1", "F-001")
    assert classify_case_failure(case, response) == []


@pytest.mark.asyncio
async def test_filter_broken_profile_is_classified_from_evidence() -> None:
    case, response = await response_for("filter-broken-v1", "F-001")
    failures = classify_case_failure(case, response)
    assert failures[0].failure_type == FailureType.FILTER_VIOLATION
    assert failures[0].evidence.observed_facts
    assert failures[0].evidence.possible_causes
    assert failures[0].evidence.recommended_investigation
    assert failures[0].evidence.recommended_fix == []


@pytest.mark.asyncio
async def test_retrieval_broken_profile_is_not_misclassified_as_ranking() -> None:
    case, response = await response_for("retrieval-broken-v1", "F-001")
    failures = classify_case_failure(case, response)
    assert failures[0].failure_type == FailureType.RETRIEVAL_MISS


@pytest.mark.asyncio
async def test_ranking_broken_profile_preserves_candidates_but_changes_order() -> None:
    case, response = await response_for("ranking-broken-v1", "RET-001")
    failures = classify_case_failure(case, response)
    assert failures[0].failure_type == FailureType.RANKING_FAILURE


@pytest.mark.asyncio
async def test_parser_regression_is_earliest_observable_failure() -> None:
    case, response = await response_for("query-parser-regression-v1", "F-001")
    failures = classify_case_failure(case, response)
    assert failures[0].failure_type == FailureType.QUERY_UNDERSTANDING


@pytest.mark.asyncio
async def test_latency_regression_is_classified_operationally() -> None:
    case, response = await response_for("latency-regression-v1", "F-001")
    failures = classify_case_failure(case, response)
    assert failures[0].failure_type == FailureType.LATENCY_FAILURE
    assert response.latency_ms >= 1000


@pytest.mark.asyncio
async def test_catalog_quality_case_is_evidence_labeled() -> None:
    case, response = await response_for("healthy-v1", "CQ-002")
    failures = classify_case_failure(case, response)
    assert failures[0].failure_type == FailureType.CATALOG_DATA_QUALITY


@pytest.mark.asyncio
async def test_failure_injection_is_deterministic() -> None:
    case = case_by_id("RET-001")
    adapter = adapter_for("ranking-broken-v1")
    first = await adapter.search(SearchRequest(query=case.query, top_k=100, seed=7))
    second = await adapter.search(SearchRequest(query=case.query, top_k=100, seed=7))
    assert [item.product.product_id for item in first.products] == [
        item.product.product_id for item in second.products
    ]

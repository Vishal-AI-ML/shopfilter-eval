from pathlib import Path

import pytest

from packages.demo_search.engine import DemoSearchEngine
from packages.evaluation_engine.catalog import load_catalog
from packages.evaluation_engine.datasets import (
    EXPECTED_DISTRIBUTION,
    GoldenDatasetError,
    ReviewStatus,
    compute_dataset_hash,
    load_golden_dataset,
    validate_golden_dataset,
)
from packages.evaluation_engine.models import SearchRequest
from packages.evaluation_engine.query_parser import parse_query
from packages.search_adapters.demo import DemoSearchAdapter

ROOT = Path(__file__).parents[2]
CATALOG_PATH = ROOT / "data" / "demo" / "catalog-v1.json"
DATASET_PATH = ROOT / "data" / "goldens" / "golden-v1.json"


def test_golden_dataset_has_published_contract() -> None:
    catalog = load_catalog(CATALOG_PATH)
    dataset = load_golden_dataset(DATASET_PATH)
    report = validate_golden_dataset(dataset, catalog, require_approved=True)

    assert dataset.version == "v1"
    assert dataset.status == ReviewStatus.APPROVED
    assert report["case_count"] == 20
    assert report["distribution"] == {
        case_type.value: count for case_type, count in EXPECTED_DISTRIBUTION.items()
    }
    assert report["duplicate_case_ids"] == []
    assert report["missing_product_ids"] == []
    assert report["approved_cases"] == 20
    assert report["all_approved"] is True
    assert report["hash_valid"] is True


def test_every_case_matches_deterministic_parser() -> None:
    dataset = load_golden_dataset(DATASET_PATH)
    for case in dataset.cases:
        parsed = parse_query(case.query)
        assert parsed.query_text == case.expected_query_text, case.case_id
        assert parsed.constraints == case.expected_constraints, case.case_id
        assert parsed.sorting_intent == case.expected_sorting_intent, case.case_id


@pytest.mark.asyncio
async def test_positive_cases_match_demo_adapter_results() -> None:
    catalog = load_catalog(CATALOG_PATH)
    dataset = load_golden_dataset(DATASET_PATH)
    adapter = DemoSearchAdapter(DemoSearchEngine(catalog))

    for case in dataset.cases:
        if not case.expected_products:
            continue
        response = await adapter.search(SearchRequest(query=case.query, top_k=100))
        actual_ids = [result.product.product_id for result in response.products]
        expected_ids = [expected.product_id for expected in case.expected_products]
        assert actual_ids == expected_ids, case.case_id
        for expected in case.expected_products:
            if expected.expected_rank is not None:
                assert actual_ids[expected.expected_rank - 1] == expected.product_id


def test_in_review_dataset_cannot_be_published() -> None:
    catalog = load_catalog(CATALOG_PATH)
    dataset = load_golden_dataset(DATASET_PATH)
    in_review = dataset.model_copy(update={"status": ReviewStatus.IN_REVIEW})
    in_review = in_review.model_copy(
        update={"content_hash": compute_dataset_hash(in_review)}
    )
    with pytest.raises(GoldenDatasetError, match="not fully human-approved"):
        validate_golden_dataset(in_review, catalog, require_approved=True)


def test_tampered_dataset_hash_is_rejected() -> None:
    catalog = load_catalog(CATALOG_PATH)
    dataset = load_golden_dataset(DATASET_PATH)
    tampered_case = dataset.cases[0].model_copy(update={"query": "tampered query"})
    tampered = dataset.model_copy(update={"cases": [tampered_case, *dataset.cases[1:]]})

    with pytest.raises(GoldenDatasetError, match="hash does not match"):
        validate_golden_dataset(tampered, catalog)


def test_duplicate_case_ids_are_rejected() -> None:
    catalog = load_catalog(CATALOG_PATH)
    dataset = load_golden_dataset(DATASET_PATH)
    duplicate = dataset.model_copy(update={"cases": [*dataset.cases, dataset.cases[0]]})
    duplicate = duplicate.model_copy(update={"content_hash": compute_dataset_hash(duplicate)})

    with pytest.raises(GoldenDatasetError, match="Duplicate case IDs"):
        validate_golden_dataset(duplicate, catalog)

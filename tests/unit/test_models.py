from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from packages.evaluation_engine.models import (
    Availability,
    Catalog,
    EvaluationCase,
    EvaluationRunMetadata,
    ExpectedProduct,
    Product,
    RankedProductResult,
    RelevanceLabel,
    RunStatus,
    SearchConstraints,
    SearchRequest,
)


def make_product(product_id: str = "p-001") -> Product:
    return Product(
        product_id=product_id,
        title="Black Running Shoe",
        category="shoes",
        price=Decimal("2499.00"),
        currency="inr",
        availability=Availability.IN_STOCK,
        field_provenance={"color": "source"},
    )


def test_product_normalizes_currency() -> None:
    product = make_product()
    assert product.currency == "INR"


@pytest.mark.parametrize("product_id", ["", "   "])
def test_product_rejects_blank_id(product_id: str) -> None:
    with pytest.raises(ValidationError):
        make_product(product_id)


def test_product_rejects_negative_price() -> None:
    with pytest.raises(ValidationError):
        Product(
            product_id="p-001",
            title="Shoe",
            category="shoes",
            price=Decimal(-1),
            currency="INR",
        )


def test_product_rejects_invalid_currency() -> None:
    with pytest.raises(ValidationError):
        Product(
            product_id="p-001",
            title="Shoe",
            category="shoes",
            price=Decimal(1),
            currency="rupees",
        )


def test_catalog_rejects_duplicate_product_ids() -> None:
    with pytest.raises(ValidationError):
        Catalog(
            catalog_id="demo",
            version="v1",
            products=[make_product("p-001"), make_product("p-001")],
        )


def test_search_request_rejects_blank_query() -> None:
    with pytest.raises(ValidationError):
        SearchRequest(query="   ")


def test_rank_starts_at_one() -> None:
    with pytest.raises(ValidationError):
        RankedProductResult(product=make_product(), rank=0, score=1.0)


def test_score_cannot_be_negative() -> None:
    with pytest.raises(ValidationError):
        RankedProductResult(product=make_product(), rank=1, score=-0.1)


def test_constraints_reject_inverted_price_range() -> None:
    with pytest.raises(ValidationError):
        SearchConstraints(min_price=Decimal(5000), max_price=Decimal(1000))


def test_relevance_label_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError):
        ExpectedProduct(product_id="p-001", relevance="UNKNOWN")


def test_evaluation_case_rejects_blank_query() -> None:
    with pytest.raises(ValidationError):
        EvaluationCase(case_id="case-1", query="")


def test_json_round_trip() -> None:
    run = EvaluationRunMetadata(
        run_id="run-1",
        project_id="project-1",
        dataset_version="golden-v1",
        catalog_version="catalog-v1",
        search_system_version="demo-v1",
        adapter_version="adapter-v1",
        metric_definition_version="metrics-v1",
        git_sha="abc123",
        started_at=datetime(2026, 9, 22, tzinfo=UTC),
        status=RunStatus.RUNNING,
    )

    restored = EvaluationRunMetadata.model_validate_json(run.model_dump_json())
    assert restored == run


def test_expected_product_round_trip() -> None:
    expected = ExpectedProduct(product_id="p-001", relevance=RelevanceLabel.EXACT)
    restored = ExpectedProduct.model_validate_json(expected.model_dump_json())
    assert restored == expected

from __future__ import annotations

from decimal import Decimal

import pytest

from packages.demo_search.engine import DemoSearchEngine
from packages.esci_pipeline.review import (
    SourceValidatedCase,
    SourceValidatedDataset,
)
from packages.evaluation_engine.models import (
    Availability,
    Catalog,
    ExpectedProduct,
    Product,
    RelevanceLabel,
)
from packages.evaluation_engine.runner import EvaluationCancelled
from packages.search_adapters.demo import DemoSearchAdapter
from services.worker.source_validated_runner import SourceValidatedEvaluationRunner


def _product(product_id: str, title: str) -> Product:
    return Product(
        product_id=product_id,
        title=title,
        category="shoes",
        price=Decimal(1000),
        currency="INR",
        availability=Availability.IN_STOCK,
    )


def _dataset() -> tuple[Catalog, SourceValidatedDataset]:
    catalog = Catalog(
        catalog_id="source-catalog",
        version="v1",
        products=[
            _product("shoe-1", "black running shoes"),
            _product("shoe-2", "blue walking shoes"),
        ],
    )
    cases = [
        SourceValidatedCase(
            case_id="case-1",
            query_id=1,
            query="black running shoes",
            split="train",
            expected_products=[
                ExpectedProduct(product_id="shoe-1", relevance=RelevanceLabel.EXACT)
            ],
            source_provenance={"source": "test"},
        ),
        SourceValidatedCase(
            case_id="case-2",
            query_id=2,
            query="blue walking shoes",
            split="test",
            expected_products=[
                ExpectedProduct(product_id="shoe-2", relevance=RelevanceLabel.EXACT)
            ],
            source_provenance={"source": "test"},
        ),
    ]
    dataset = SourceValidatedDataset(
        dataset_id="source-dataset",
        version="v1",
        catalog_id=catalog.catalog_id,
        catalog_version=catalog.version,
        source_manifest_id="manifest-v1",
        source_draft_hash="a" * 64,
        source_catalog_hash="b" * 64,
        validation_evidence={"human_reviewed": False},
        cases=cases,
        content_hash="c" * 64,
    )
    return catalog, dataset


@pytest.mark.asyncio
async def test_source_validated_runner_reports_progress_without_claiming_human_review() -> None:
    catalog, dataset = _dataset()
    completed: list[tuple[int, int]] = []
    runner = SourceValidatedEvaluationRunner(
        DemoSearchAdapter(DemoSearchEngine(catalog)), catalog
    )
    artifact = await runner.run(
        dataset,
        search_system_version="demo-v1",
        top_k=2,
        seed=42,
        progress_callback=lambda done, total: completed.append((done, total)),
    )
    assert artifact.case_count == 2
    assert completed == [(1, 2), (2, 2)]
    assert artifact.dataset_hash == dataset.content_hash
    assert "filter_accuracy" not in artifact.aggregate_metrics
    assert all(not case.failures for case in artifact.cases)


@pytest.mark.asyncio
async def test_source_validated_runner_checks_cancellation_between_cases() -> None:
    catalog, dataset = _dataset()
    completed: list[tuple[int, int]] = []
    runner = SourceValidatedEvaluationRunner(
        DemoSearchAdapter(DemoSearchEngine(catalog)), catalog
    )
    with pytest.raises(EvaluationCancelled):
        await runner.run(
            dataset,
            search_system_version="demo-v1",
            top_k=2,
            seed=42,
            progress_callback=lambda done, total: completed.append((done, total)),
            cancellation_check=lambda: bool(completed),
        )
    assert completed == [(1, 2)]

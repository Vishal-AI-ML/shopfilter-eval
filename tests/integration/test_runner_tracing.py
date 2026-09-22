from pathlib import Path

import pytest

from packages.demo_search.engine import DemoSearchEngine
from packages.evaluation_engine.catalog import load_catalog
from packages.evaluation_engine.datasets import load_golden_dataset
from packages.evaluation_engine.runner import EvaluationRunner
from packages.search_adapters.demo import DemoSearchAdapter
from packages.tracing import InMemoryTraceProvider, NoOpTraceProvider

ROOT = Path(__file__).parents[2]
CATALOG_PATH = ROOT / "data" / "demo" / "catalog-v1.json"
DATASET_PATH = ROOT / "data" / "goldens" / "golden-v1.json"
REQUIRED_SPANS = [
    "query-understanding",
    "search-adapter",
    "retrieval",
    "filtering",
    "ranking",
    "deterministic-evaluation",
    "failure-classification",
]


@pytest.mark.asyncio
async def test_runner_records_complete_case_traces() -> None:
    catalog = load_catalog(CATALOG_PATH)
    dataset = load_golden_dataset(DATASET_PATH)
    provider = InMemoryTraceProvider()
    runner = EvaluationRunner(
        DemoSearchAdapter(DemoSearchEngine(catalog)),
        catalog,
        provider,
    )

    artifact = await runner.run(dataset, search_system_version="demo-v1")

    assert artifact.trace_provider == "memory"
    assert len(provider.traces) == 20
    assert all(case.trace_id is not None for case in artifact.cases)
    first_trace = provider.traces[0]
    assert [span.name for span in first_trace.spans] == REQUIRED_SPANS
    assert first_trace.run_id == artifact.run_id
    assert first_trace.case_id == artifact.cases[0].case_id


@pytest.mark.asyncio
async def test_noop_tracing_does_not_change_evaluation_outcome() -> None:
    catalog = load_catalog(CATALOG_PATH)
    dataset = load_golden_dataset(DATASET_PATH)
    runner = EvaluationRunner(
        DemoSearchAdapter(DemoSearchEngine(catalog)),
        catalog,
        NoOpTraceProvider(),
    )

    artifact = await runner.run(dataset, search_system_version="demo-v1")

    assert artifact.trace_provider == "noop"
    assert artifact.passed_case_count == 19
    assert artifact.failed_case_count == 1
    assert all(case.trace_id is None for case in artifact.cases)

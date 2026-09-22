from pathlib import Path

import pytest

from packages.demo_search.engine import DemoSearchEngine
from packages.evaluation_engine.catalog import load_catalog
from packages.evaluation_engine.datasets import GoldenDataset, load_golden_dataset
from packages.evaluation_engine.runner import EvaluationRunner, write_run_artifact
from packages.search_adapters.demo import DemoSearchAdapter

ROOT = Path(__file__).parents[2]
CATALOG_PATH = ROOT / "data" / "demo" / "catalog-v1.json"
DATASET_PATH = ROOT / "data" / "goldens" / "golden-v1.json"


def make_runner() -> tuple[EvaluationRunner, GoldenDataset]:
    catalog = load_catalog(CATALOG_PATH)
    dataset = load_golden_dataset(DATASET_PATH)
    adapter = DemoSearchAdapter(DemoSearchEngine(catalog))
    return EvaluationRunner(adapter, catalog), dataset


@pytest.mark.asyncio
async def test_twenty_cases_run_end_to_end() -> None:
    runner, dataset = make_runner()
    artifact = await runner.run(
        dataset,
        search_system_version="demo-v1",
        top_k=10,
        seed=0,
    )

    assert artifact.case_count == 20
    assert artifact.passed_case_count == 19
    assert artifact.failed_case_count == 1
    assert len(artifact.cases) == 20
    assert artifact.aggregate_metrics["precision_at_10"] is not None
    assert artifact.aggregate_metrics["recall_at_10"] is not None
    assert artifact.aggregate_metrics["ndcg_at_10"] is not None
    assert artifact.aggregate_metrics["mrr"] is not None
    assert artifact.aggregate_metrics["filter_accuracy"] is not None


def test_make_runner_dataset_type_is_runtime_valid() -> None:
    _, dataset = make_runner()
    assert dataset.version == "v1"


@pytest.mark.asyncio
async def test_false_positives_and_false_negatives_are_separate() -> None:
    runner, dataset = make_runner()
    artifact = await runner.run(dataset, search_system_version="demo-v1")
    catalog_gap = next(case for case in artifact.cases if case.case_id == "CQ-002")

    assert catalog_gap.false_positives == [
        "SHOE-001",
        "SHOE-007",
        "SHOE-013",
        "SHOE-019",
        "SHOE-025",
        "SHOE-031",
    ]
    assert catalog_gap.false_negatives == []
    assert catalog_gap.passed is False


@pytest.mark.asyncio
async def test_same_configuration_has_stable_identity_and_results() -> None:
    runner, dataset = make_runner()
    first = await runner.run(dataset, search_system_version="demo-v1", top_k=10, seed=7)
    second = await runner.run(dataset, search_system_version="demo-v1", top_k=10, seed=7)

    assert first.run_id == second.run_id
    assert first.result_fingerprint == second.result_fingerprint
    assert first.aggregate_metrics == second.aggregate_metrics
    assert first.cases == second.cases


@pytest.mark.asyncio
async def test_run_artifact_is_written_and_reused_immutably(tmp_path: Path) -> None:
    runner, dataset = make_runner()
    artifact = await runner.run(dataset, search_system_version="demo-v1")

    first_path = write_run_artifact(artifact, tmp_path)
    second_path = write_run_artifact(artifact, tmp_path)

    assert first_path == second_path
    restored = type(artifact).model_validate_json(first_path.read_text(encoding="utf-8"))
    assert restored == artifact


@pytest.mark.asyncio
async def test_conflicting_artifact_cannot_overwrite_existing_file(tmp_path: Path) -> None:
    runner, dataset = make_runner()
    artifact = await runner.run(dataset, search_system_version="demo-v1")
    write_run_artifact(artifact, tmp_path)
    conflict = artifact.model_copy(update={"result_fingerprint": "0" * 64})

    with pytest.raises(FileExistsError, match="Immutable run artifact conflict"):
        write_run_artifact(conflict, tmp_path)

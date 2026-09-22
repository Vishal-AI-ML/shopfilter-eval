from pathlib import Path

import pytest

from packages.demo_search.engine import DemoSearchEngine
from packages.evaluation_engine.catalog import load_catalog
from packages.evaluation_engine.datasets import load_golden_dataset
from packages.evaluation_engine.runner import EvaluationRunArtifact, EvaluationRunner
from packages.search_adapters.demo import DemoSearchAdapter
from packages.search_adapters.faults import (
    FaultInjectingSearchAdapter,
    load_failure_profiles,
)

ROOT = Path(__file__).parents[2]
CATALOG_PATH = ROOT / "data" / "demo" / "catalog-v1.json"
DATASET_PATH = ROOT / "data" / "goldens" / "golden-v1.json"


async def run_profile(profile_id: str) -> EvaluationRunArtifact:
    catalog = load_catalog(CATALOG_PATH)
    dataset = load_golden_dataset(DATASET_PATH)
    base = DemoSearchAdapter(DemoSearchEngine(catalog))
    adapter = FaultInjectingSearchAdapter(
        base,
        catalog,
        load_failure_profiles()[profile_id],
    )
    return await EvaluationRunner(adapter, catalog).run(
        dataset,
        search_system_version=profile_id,
        top_k=10,
        seed=0,
    )


@pytest.mark.asyncio
async def test_healthy_and_broken_profiles_have_distinct_run_identity() -> None:
    healthy = await run_profile("healthy-v1")
    broken = await run_profile("filter-broken-v1")
    assert healthy.run_id != broken.run_id
    assert healthy.result_fingerprint != broken.result_fingerprint
    assert broken.failed_case_count > healthy.failed_case_count
    assert broken.failure_counts["FILTER_VIOLATION"] > 0


@pytest.mark.asyncio
async def test_retrieval_and_ranking_profiles_remain_distinguishable() -> None:
    retrieval = await run_profile("retrieval-broken-v1")
    ranking = await run_profile("ranking-broken-v1")
    assert retrieval.failure_counts["RETRIEVAL_MISS"] > 0
    assert ranking.failure_counts["RANKING_FAILURE"] > 0

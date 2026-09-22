from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from packages.evaluation_engine.datasets import (
    GoldenCase,
    GoldenDataset,
    validate_golden_dataset,
)
from packages.evaluation_engine.metrics import (
    constraint_satisfaction,
    false_negative_rate,
    false_positive_rate,
    filter_accuracy,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    query_understanding_field_accuracy,
    recall_at_k,
    reciprocal_rank,
    relevant_result_displacement,
    top_result_correctness,
)
from packages.evaluation_engine.models import (
    Catalog,
    MetricResult,
    ParsedIntent,
    SearchRequest,
)
from packages.search_adapters.base import SearchAdapter

METRIC_DEFINITION_VERSION = "deterministic-v1"
RELEVANCE_GRADES = {"E": 3, "S": 2, "C": 1, "I": 0}


class CaseEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    query: str
    expected_product_ids: list[str]
    actual_product_ids: list[str]
    false_positives: list[str]
    false_negatives: list[str]
    metrics: list[MetricResult]
    passed: bool


class EvaluationRunArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    run_id: str
    result_fingerprint: str
    dataset_id: str
    dataset_version: str
    dataset_hash: str
    catalog_id: str
    catalog_version: str
    search_system_version: str
    adapter_provider: str
    metric_definition_version: str
    top_k: int = Field(ge=1)
    seed: int
    case_count: int
    passed_case_count: int
    failed_case_count: int
    aggregate_metrics: dict[str, float | None]
    cases: list[CaseEvaluationResult]


def _canonical_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _metric_values(
    case_results: list[CaseEvaluationResult],
) -> dict[str, list[float]]:
    values: dict[str, list[float]] = defaultdict(list)
    for case_result in case_results:
        for metric in case_result.metrics:
            if metric.value is not None:
                values[metric.metric_name].append(metric.value)
    return values


def _mean(values: list[float]) -> float | None:
    return None if not values else sum(values) / len(values)


def _expected_intent(case: GoldenCase) -> ParsedIntent:
    return ParsedIntent(
        query_text=case.expected_query_text,
        constraints=case.expected_constraints,
        sorting_intent=case.expected_sorting_intent,
    )


def _relevance_grades(case: GoldenCase) -> dict[str, int]:
    return {
        expected.product_id: RELEVANCE_GRADES[expected.relevance.value]
        for expected in case.expected_products
    }


class EvaluationRunner:
    def __init__(self, adapter: SearchAdapter, catalog: Catalog) -> None:
        self.adapter = adapter
        self.catalog = catalog

    async def _evaluate_case(
        self,
        case: GoldenCase,
        *,
        top_k: int,
        seed: int,
    ) -> CaseEvaluationResult:
        response = await self.adapter.search(
            SearchRequest(query=case.query, top_k=top_k, seed=seed)
        )
        expected_ids = [expected.product_id for expected in case.expected_products]
        relevant_ids = set(expected_ids)
        actual_ids = [result.product.product_id for result in response.products]
        false_positives = [
            product_id for product_id in actual_ids if product_id not in relevant_ids
        ]
        false_negatives = sorted(relevant_ids - set(actual_ids))
        actual_intent = response.interpreted_query
        metrics: list[MetricResult] = []
        if actual_intent is not None:
            metrics.append(
                query_understanding_field_accuracy(_expected_intent(case), actual_intent)
            )
        metrics.extend(
            [
                filter_accuracy(case.expected_constraints, response.applied_filters),
                constraint_satisfaction(
                    [result.product for result in response.products],
                    case.expected_constraints,
                ),
                precision_at_k(actual_ids, relevant_ids, top_k),
                recall_at_k(actual_ids, relevant_ids, top_k),
                false_positive_rate(actual_ids, relevant_ids),
                false_negative_rate(actual_ids, relevant_ids),
                reciprocal_rank(actual_ids, relevant_ids),
                ndcg_at_k(actual_ids, _relevance_grades(case), top_k),
                top_result_correctness(actual_ids, relevant_ids),
                relevant_result_displacement(actual_ids, expected_ids),
            ]
        )
        return CaseEvaluationResult(
            case_id=case.case_id,
            query=case.query,
            expected_product_ids=expected_ids,
            actual_product_ids=actual_ids,
            false_positives=false_positives,
            false_negatives=false_negatives,
            metrics=metrics,
            passed=actual_ids == expected_ids,
        )

    async def run(
        self,
        dataset: GoldenDataset,
        *,
        search_system_version: str,
        top_k: int = 10,
        seed: int = 0,
    ) -> EvaluationRunArtifact:
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        validate_golden_dataset(dataset, self.catalog, require_approved=True)
        run_config = {
            "dataset_hash": dataset.content_hash,
            "catalog_id": self.catalog.catalog_id,
            "catalog_version": self.catalog.version,
            "search_system_version": search_system_version,
            "adapter_provider": self.adapter.provider_name,
            "metric_definition_version": METRIC_DEFINITION_VERSION,
            "top_k": top_k,
            "seed": seed,
        }
        run_id = f"run-{_canonical_hash(run_config)[:16]}"
        case_results = [
            await self._evaluate_case(case, top_k=top_k, seed=seed)
            for case in dataset.cases
        ]
        metric_values = _metric_values(case_results)
        reciprocal_ranks = metric_values.get("reciprocal_rank", [])
        mrr = mean_reciprocal_rank(reciprocal_ranks)
        aggregate_metrics = {
            f"precision_at_{top_k}": _mean(metric_values.get(f"precision_at_{top_k}", [])),
            f"recall_at_{top_k}": _mean(metric_values.get(f"recall_at_{top_k}", [])),
            f"ndcg_at_{top_k}": _mean(metric_values.get(f"ndcg_at_{top_k}", [])),
            "mrr": mrr.value,
            "filter_accuracy": _mean(metric_values.get("filter_accuracy", [])),
            "false_positive_rate": _mean(metric_values.get("false_positive_rate", [])),
            "false_negative_rate": _mean(metric_values.get("false_negative_rate", [])),
            "query_understanding_field_accuracy": _mean(
                metric_values.get("query_understanding_field_accuracy", [])
            ),
        }
        passed_count = sum(case_result.passed for case_result in case_results)
        stable_results = {
            "run_config": run_config,
            "aggregate_metrics": aggregate_metrics,
            "cases": [
                case_result.model_dump(mode="json") for case_result in case_results
            ],
        }
        fingerprint = _canonical_hash(stable_results)
        return EvaluationRunArtifact(
            run_id=run_id,
            result_fingerprint=fingerprint,
            dataset_id=dataset.dataset_id,
            dataset_version=dataset.version,
            dataset_hash=dataset.content_hash,
            catalog_id=self.catalog.catalog_id,
            catalog_version=self.catalog.version,
            search_system_version=search_system_version,
            adapter_provider=self.adapter.provider_name,
            metric_definition_version=METRIC_DEFINITION_VERSION,
            top_k=top_k,
            seed=seed,
            case_count=len(case_results),
            passed_case_count=passed_count,
            failed_case_count=len(case_results) - passed_count,
            aggregate_metrics=aggregate_metrics,
            cases=case_results,
        )


def write_run_artifact(
    artifact: EvaluationRunArtifact,
    artifact_directory: str | Path,
) -> Path:
    directory = Path(artifact_directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{artifact.run_id}.json"
    content = artifact.model_dump_json(indent=2)
    if path.exists():
        existing = EvaluationRunArtifact.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        if existing.result_fingerprint != artifact.result_fingerprint:
            raise FileExistsError(
                f"Immutable run artifact conflict for {artifact.run_id}"
            )
        return path
    temporary_path = path.with_suffix(".json.tmp")
    temporary_path.write_text(content, encoding="utf-8")
    temporary_path.replace(path)
    return path

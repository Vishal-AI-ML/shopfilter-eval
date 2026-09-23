from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Callable

from packages.esci_pipeline.review import SourceValidatedDataset
from packages.evaluation_engine.metrics import (
    false_negative_rate,
    false_positive_rate,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    relevant_result_displacement,
    top_result_correctness,
)
from packages.evaluation_engine.models import Catalog, SearchRequest
from packages.evaluation_engine.runner import (
    METRIC_DEFINITION_VERSION,
    CaseEvaluationResult,
    EvaluationCancelled,
    EvaluationRunArtifact,
)
from packages.search_adapters.base import SearchAdapter
from packages.tracing import NoOpTraceProvider, TraceProvider

_RELEVANCE_GRADES = {"E": 3, "S": 2, "C": 1, "I": 0}


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _mean(values: list[float]) -> float | None:
    return None if not values else sum(values) / len(values)


class SourceValidatedEvaluationRunner:
    """Run deterministic relevance metrics without claiming human review."""

    def __init__(
        self,
        adapter: SearchAdapter,
        catalog: Catalog,
        trace_provider: TraceProvider | None = None,
    ) -> None:
        self.adapter = adapter
        self.catalog = catalog
        self.trace_provider = trace_provider or NoOpTraceProvider()

    async def run(
        self,
        dataset: SourceValidatedDataset,
        *,
        search_system_version: str,
        top_k: int,
        seed: int,
        progress_callback: Callable[[int, int], None] | None = None,
        cancellation_check: Callable[[], bool] | None = None,
    ) -> EvaluationRunArtifact:
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        if dataset.catalog_id != self.catalog.catalog_id:
            raise ValueError("Dataset and catalog IDs do not match")
        if dataset.catalog_version != self.catalog.version:
            raise ValueError("Dataset and catalog versions do not match")
        run_config = {
            "dataset_hash": dataset.content_hash,
            "dataset_status": dataset.status,
            "catalog_id": self.catalog.catalog_id,
            "catalog_version": self.catalog.version,
            "search_system_version": search_system_version,
            "adapter_provider": self.adapter.provider_name,
            "trace_provider": self.trace_provider.provider_name,
            "metric_definition_version": METRIC_DEFINITION_VERSION,
            "top_k": top_k,
            "seed": seed,
        }
        run_id = f"run-{_canonical_hash(run_config)[:16]}"
        case_results: list[CaseEvaluationResult] = []
        metric_values: dict[str, list[float]] = defaultdict(list)
        total_cases = len(dataset.cases)
        for completed, case in enumerate(dataset.cases, start=1):
            if cancellation_check is not None and cancellation_check():
                raise EvaluationCancelled("Evaluation cancellation requested")
            trace = self.trace_provider.start_case(
                run_id=run_id,
                case_id=case.case_id,
                query=case.query,
                metadata={
                    "dataset_status": "SOURCE_VALIDATED",
                    "human_reviewed": False,
                },
            )
            response = await self.adapter.search(
                SearchRequest(query=case.query, top_k=top_k, seed=seed)
            )
            actual_ids = [result.product.product_id for result in response.products]
            grades = {
                expected.product_id: _RELEVANCE_GRADES[expected.relevance.value]
                for expected in case.expected_products
            }
            relevant_ids = {
                product_id for product_id, grade in grades.items() if grade > 0
            }
            expected_ids = [
                expected.product_id
                for expected in case.expected_products
                if _RELEVANCE_GRADES[expected.relevance.value] > 0
            ]
            metrics = [
                precision_at_k(actual_ids, relevant_ids, top_k),
                recall_at_k(actual_ids, relevant_ids, top_k),
                false_positive_rate(actual_ids, relevant_ids),
                false_negative_rate(actual_ids, relevant_ids),
                reciprocal_rank(actual_ids, relevant_ids),
                ndcg_at_k(actual_ids, grades, top_k),
                top_result_correctness(actual_ids, relevant_ids),
                relevant_result_displacement(actual_ids, expected_ids),
            ]
            for metric in metrics:
                if metric.value is not None:
                    metric_values[metric.metric_name].append(metric.value)
            false_positives = [item for item in actual_ids if item not in relevant_ids]
            false_negatives = sorted(relevant_ids - set(actual_ids))
            passed = bool(actual_ids and actual_ids[0] in relevant_ids)
            trace.record_span(
                "search-adapter",
                output_data={
                    "provider": response.provider,
                    "latency_ms": response.latency_ms,
                },
            )
            trace.record_span(
                "retrieval", output_data={"candidate_ids": actual_ids}
            )
            trace.record_span(
                "deterministic-evaluation",
                output_data={
                    "dataset_status": "SOURCE_VALIDATED",
                    "human_reviewed": False,
                    "metrics": [
                        {"name": metric.metric_name, "value": metric.value}
                        for metric in metrics
                    ],
                },
            )
            trace_reference = trace.finish(output_data={"passed": passed})
            case_results.append(
                CaseEvaluationResult(
                    case_id=case.case_id,
                    query=case.query,
                    expected_product_ids=expected_ids,
                    actual_product_ids=actual_ids,
                    false_positives=false_positives,
                    false_negatives=false_negatives,
                    metrics=metrics,
                    failures=[],
                    trace_id=(
                        trace_reference.trace_id
                        if trace_reference is not None
                        else None
                    ),
                    trace_url=(
                        trace_reference.trace_url
                        if trace_reference is not None
                        else None
                    ),
                    passed=passed,
                )
            )
            if progress_callback is not None:
                progress_callback(completed, total_cases)

        mrr = mean_reciprocal_rank(metric_values.get("reciprocal_rank", []))
        aggregate_metrics = {
            f"precision_at_{top_k}": _mean(
                metric_values.get(f"precision_at_{top_k}", [])
            ),
            f"recall_at_{top_k}": _mean(
                metric_values.get(f"recall_at_{top_k}", [])
            ),
            f"ndcg_at_{top_k}": _mean(metric_values.get(f"ndcg_at_{top_k}", [])),
            "mrr": mrr.value,
            "false_positive_rate": _mean(
                metric_values.get("false_positive_rate", [])
            ),
            "false_negative_rate": _mean(
                metric_values.get("false_negative_rate", [])
            ),
        }
        passed_count = sum(case_result.passed for case_result in case_results)
        stable_results = {
            "run_config": run_config,
            "aggregate_metrics": aggregate_metrics,
            "cases": [case.model_dump(mode="json") for case in case_results],
        }
        return EvaluationRunArtifact(
            run_id=run_id,
            result_fingerprint=_canonical_hash(stable_results),
            dataset_id=dataset.dataset_id,
            dataset_version=dataset.version,
            dataset_hash=dataset.content_hash,
            catalog_id=self.catalog.catalog_id,
            catalog_version=self.catalog.version,
            search_system_version=search_system_version,
            adapter_provider=self.adapter.provider_name,
            trace_provider=self.trace_provider.provider_name,
            metric_definition_version=METRIC_DEFINITION_VERSION,
            top_k=top_k,
            seed=seed,
            case_count=len(case_results),
            passed_case_count=passed_count,
            failed_case_count=len(case_results) - passed_count,
            aggregate_metrics=aggregate_metrics,
            failure_counts={},
            cases=case_results,
        )

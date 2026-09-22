from __future__ import annotations

from packages.evaluation_engine.datasets import CaseType, GoldenCase
from packages.evaluation_engine.metrics import (
    constraint_satisfaction,
    filter_accuracy,
    query_understanding_field_accuracy,
)
from packages.evaluation_engine.models import (
    Failure,
    FailureEvidence,
    FailureType,
    ParsedIntent,
    SearchResponse,
)
from packages.search_adapters.base import SearchAdapterError


def _failure(
    failure_type: FailureType,
    *,
    severity: str,
    component: str,
    confidence: float,
    facts: list[str],
    possible_causes: list[str],
    investigations: list[str],
) -> Failure:
    return Failure(
        failure_type=failure_type,
        severity=severity,
        component=component,
        confidence=confidence,
        evidence=FailureEvidence(
            observed_facts=facts,
            possible_causes=possible_causes,
            recommended_investigation=investigations,
            recommended_fix=[],
        ),
    )


def classify_adapter_error(error: SearchAdapterError) -> Failure:
    return _failure(
        FailureType.SYSTEM_ERROR,
        severity="high",
        component="search_adapter",
        confidence=1.0,
        facts=[
            f"Adapter {error.provider} returned normalized error {error.code.value}",
            f"Retryable: {error.retryable}",
        ],
        possible_causes=["The provider or adapter boundary may be unavailable"],
        investigations=["Inspect provider health and sanitized adapter logs"],
    )


def classify_case_failure(
    case: GoldenCase,
    response: SearchResponse,
    *,
    latency_threshold_ms: float = 500.0,
) -> list[Failure]:
    expected_intent = ParsedIntent(
        query_text=case.expected_query_text,
        constraints=case.expected_constraints,
        sorting_intent=case.expected_sorting_intent,
    )
    actual_ids = [result.product.product_id for result in response.products]
    expected_ids = [expected.product_id for expected in case.expected_products]
    relevant_ids = set(expected_ids)
    retrieved_ids = set(response.retrieved_candidates or [])
    filtered_ids = set(response.filtered_candidates or [])

    if response.interpreted_query is None:
        return [
            _failure(
                FailureType.QUERY_UNDERSTANDING,
                severity="high",
                component="query_understanding",
                confidence=1.0,
                facts=["Interpreted query evidence was unavailable"],
                possible_causes=["The provider may not expose interpreted-query evidence"],
                investigations=["Verify adapter trace capabilities and parser output"],
            )
        ]

    intent_metric = query_understanding_field_accuracy(
        expected_intent,
        response.interpreted_query,
    )
    if intent_metric.value is not None and intent_metric.value < 1.0:
        return [
            _failure(
                FailureType.QUERY_UNDERSTANDING,
                severity="high",
                component="query_understanding",
                confidence=1.0,
                facts=[
                    "Expected and interpreted query fields differ",
                    f"Mismatches: {intent_metric.evidence.observed.get('mismatches', {})}",
                ],
                possible_causes=["A parser rule or vocabulary may have regressed"],
                investigations=["Compare parser version, aliases and normalized intent"],
            )
        ]

    filter_metric = filter_accuracy(
        case.expected_constraints,
        response.applied_filters,
    )
    if filter_metric.value is not None and filter_metric.value < 1.0:
        return [
            _failure(
                FailureType.FILTER_EXTRACTION,
                severity="high",
                component="filtering",
                confidence=1.0,
                facts=[
                    "Expected and applied filters differ",
                    f"Mismatches: {filter_metric.evidence.observed.get('mismatches', {})}",
                ],
                possible_causes=["Filter mapping may have dropped or changed a constraint"],
                investigations=["Inspect applied-filter mapping and adapter response"],
            )
        ]

    if (
        case.case_type == CaseType.CATALOG_QUALITY
        and not expected_ids
        and actual_ids
    ):
        return [
            _failure(
                FailureType.CATALOG_DATA_QUALITY,
                severity="medium",
                component="catalog",
                confidence=0.9,
                facts=[
                    "The reviewed case has no expected matching product",
                    f"Returned product IDs: {actual_ids}",
                ],
                possible_causes=[
                    "The catalog or controlled vocabulary may not represent the requested attribute"
                ],
                investigations=[
                    "Inspect catalog coverage, field provenance and unsupported attributes"
                ],
            )
        ]

    constraint_metric = constraint_satisfaction(
        [result.product for result in response.products],
        case.expected_constraints,
    )
    if constraint_metric.value is not None and constraint_metric.value < 1.0:
        return [
            _failure(
                FailureType.FILTER_VIOLATION,
                severity="high",
                component="filtering",
                confidence=1.0,
                facts=[
                    "At least one returned product violates a hard constraint",
                    f"Violations: {constraint_metric.evidence.observed.get('violations', {})}",
                ],
                possible_causes=["Filtering may have been skipped or applied incorrectly"],
                investigations=["Compare filtered candidates with final returned products"],
            )
        ]

    missing_from_retrieval = sorted(relevant_ids - retrieved_ids)
    if missing_from_retrieval:
        return [
            _failure(
                FailureType.RETRIEVAL_MISS,
                severity="high",
                component="retrieval",
                confidence=1.0,
                facts=[f"Relevant products absent from retrieval: {missing_from_retrieval}"],
                possible_causes=["Candidate generation may not recall all relevant products"],
                investigations=["Inspect lexical tokens, indexes and retrieval candidate limits"],
            )
        ]

    if relevant_ids and set(actual_ids) == relevant_ids and actual_ids != expected_ids:
        return [
            _failure(
                FailureType.RANKING_FAILURE,
                severity="medium",
                component="ranking",
                confidence=1.0,
                facts=[
                    "Relevant products were retrieved but final order differs",
                    f"Expected order: {expected_ids}",
                    f"Actual order: {actual_ids}",
                ],
                possible_causes=["Ranking weights or tie-breaking may have changed"],
                investigations=["Compare score breakdowns and ranking configuration"],
            )
        ]

    irrelevant_final = [product_id for product_id in actual_ids if product_id not in relevant_ids]
    if irrelevant_final and relevant_ids.issubset(filtered_ids):
        return [
            _failure(
                FailureType.RETRIEVAL_NOISE,
                severity="medium",
                component="retrieval",
                confidence=0.9,
                facts=[f"Irrelevant final products: {irrelevant_final}"],
                possible_causes=["Candidate retrieval may be admitting excessive noise"],
                investigations=["Inspect candidate scores and relevance cutoffs"],
            )
        ]

    if response.latency_ms > latency_threshold_ms:
        return [
            _failure(
                FailureType.LATENCY_FAILURE,
                severity="medium",
                component="operational",
                confidence=1.0,
                facts=[
                    f"Latency {response.latency_ms:.2f} ms exceeded {latency_threshold_ms:.2f} ms"
                ],
                possible_causes=["One or more pipeline stages may be slower than expected"],
                investigations=["Inspect per-stage timing and provider latency"],
            )
        ]

    return []

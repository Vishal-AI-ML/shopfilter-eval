from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from packages.evaluation_engine.metrics.common import (
    build_result,
    minimum_passed,
    unknown_result,
    validate_k,
)
from packages.evaluation_engine.models import MetricResult, MetricType


def precision_at_k(
    actual_ids: Sequence[str],
    relevant_ids: set[str],
    k: int,
    *,
    threshold: float | None = None,
) -> MetricResult:
    validate_k(k)
    top_k = list(actual_ids[:k])
    hits = [product_id for product_id in top_k if product_id in relevant_ids]
    value = len(hits) / k
    return build_result(
        f"precision_at_{k}",
        MetricType.DETERMINISTIC,
        value,
        {"k": k, "top_k": top_k, "relevant_hits": hits},
        passed=minimum_passed(value, threshold),
    )


def recall_at_k(
    actual_ids: Sequence[str],
    relevant_ids: set[str],
    k: int,
    *,
    threshold: float | None = None,
) -> MetricResult:
    validate_k(k)
    if not relevant_ids:
        return unknown_result(
            f"recall_at_{k}",
            MetricType.DETERMINISTIC,
            "Recall is undefined without relevant-product labels",
            {"k": k},
        )
    top_k = list(actual_ids[:k])
    hits = sorted(set(top_k) & relevant_ids)
    missed = sorted(relevant_ids - set(top_k))
    value = len(hits) / len(relevant_ids)
    return build_result(
        f"recall_at_{k}",
        MetricType.DETERMINISTIC,
        value,
        {"k": k, "relevant_hits": hits, "missed_relevant": missed},
        passed=minimum_passed(value, threshold),
    )


def false_positive_rate(
    actual_ids: Sequence[str],
    relevant_ids: set[str],
) -> MetricResult:
    if not actual_ids:
        return unknown_result(
            "false_positive_rate",
            MetricType.DETERMINISTIC,
            "False-positive rate is undefined when no products were returned",
        )
    false_positives = [product_id for product_id in actual_ids if product_id not in relevant_ids]
    value = len(false_positives) / len(actual_ids)
    return build_result(
        "false_positive_rate",
        MetricType.DETERMINISTIC,
        value,
        {"returned": list(actual_ids), "false_positives": false_positives},
    )


def false_negative_rate(
    actual_ids: Sequence[str],
    relevant_ids: set[str],
) -> MetricResult:
    if not relevant_ids:
        return unknown_result(
            "false_negative_rate",
            MetricType.DETERMINISTIC,
            "False-negative rate is undefined without relevant-product labels",
        )
    false_negatives = sorted(relevant_ids - set(actual_ids))
    value = len(false_negatives) / len(relevant_ids)
    return build_result(
        "false_negative_rate",
        MetricType.DETERMINISTIC,
        value,
        {"false_negatives": false_negatives, "relevant_count": len(relevant_ids)},
    )


def reciprocal_rank(actual_ids: Sequence[str], relevant_ids: set[str]) -> MetricResult:
    if not relevant_ids:
        return unknown_result(
            "reciprocal_rank",
            MetricType.DETERMINISTIC,
            "Reciprocal rank is undefined without relevant-product labels",
        )
    first_rank = next(
        (rank for rank, product_id in enumerate(actual_ids, start=1) if product_id in relevant_ids),
        None,
    )
    value = 0.0 if first_rank is None else 1 / first_rank
    return build_result(
        "reciprocal_rank",
        MetricType.DETERMINISTIC,
        value,
        {"first_relevant_rank": first_rank},
    )


def mean_reciprocal_rank(reciprocal_ranks: Sequence[float]) -> MetricResult:
    if not reciprocal_ranks:
        return unknown_result(
            "mrr",
            MetricType.DETERMINISTIC,
            "MRR is undefined without case-level reciprocal ranks",
        )
    value = sum(reciprocal_ranks) / len(reciprocal_ranks)
    return build_result(
        "mrr",
        MetricType.DETERMINISTIC,
        value,
        {"case_values": list(reciprocal_ranks), "case_count": len(reciprocal_ranks)},
    )


def _dcg(product_ids: Sequence[str], relevance_grades: Mapping[str, int]) -> float:
    return sum(
        (2 ** relevance_grades.get(product_id, 0) - 1) / math.log2(rank + 1)
        for rank, product_id in enumerate(product_ids, start=1)
    )


def ndcg_at_k(
    actual_ids: Sequence[str],
    relevance_grades: Mapping[str, int],
    k: int,
    *,
    threshold: float | None = None,
) -> MetricResult:
    validate_k(k)
    positive_grades = [grade for grade in relevance_grades.values() if grade > 0]
    if not positive_grades:
        return unknown_result(
            f"ndcg_at_{k}",
            MetricType.DETERMINISTIC,
            "NDCG is undefined without positive relevance grades",
            {"k": k},
        )
    actual_top_k = list(actual_ids[:k])
    dcg = _dcg(actual_top_k, relevance_grades)
    ideal_grades = sorted(positive_grades, reverse=True)[:k]
    ideal_dcg = sum(
        (2**grade - 1) / math.log2(rank + 1)
        for rank, grade in enumerate(ideal_grades, start=1)
    )
    value = dcg / ideal_dcg
    return build_result(
        f"ndcg_at_{k}",
        MetricType.DETERMINISTIC,
        value,
        {"k": k, "dcg": dcg, "ideal_dcg": ideal_dcg, "top_k": actual_top_k},
        passed=minimum_passed(value, threshold),
    )


def top_result_correctness(
    actual_ids: Sequence[str],
    relevant_ids: set[str],
) -> MetricResult:
    if not relevant_ids:
        return unknown_result(
            "top_result_correctness",
            MetricType.DETERMINISTIC,
            "Top-result correctness is undefined without relevant-product labels",
        )
    top_result = actual_ids[0] if actual_ids else None
    value = float(top_result in relevant_ids) if top_result is not None else 0.0
    return build_result(
        "top_result_correctness",
        MetricType.DETERMINISTIC,
        value,
        {"top_result": top_result, "is_relevant": bool(value)},
        passed=bool(value),
    )


def relevant_result_displacement(
    actual_ids: Sequence[str],
    expected_order: Sequence[str],
) -> MetricResult:
    if not expected_order:
        return unknown_result(
            "relevant_result_displacement",
            MetricType.DETERMINISTIC,
            "Displacement is undefined without an expected relevance order",
        )
    actual_ranks = {product_id: rank for rank, product_id in enumerate(actual_ids, start=1)}
    missing_rank = max(len(actual_ids), len(expected_order)) + 1
    displacements = {
        product_id: max(0, actual_ranks.get(product_id, missing_rank) - expected_rank)
        for expected_rank, product_id in enumerate(expected_order, start=1)
    }
    value = sum(displacements.values()) / len(expected_order)
    return build_result(
        "relevant_result_displacement",
        MetricType.DETERMINISTIC,
        value,
        {"displacements": displacements, "missing_rank": missing_rank},
    )

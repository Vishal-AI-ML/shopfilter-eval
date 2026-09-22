from __future__ import annotations

from typing import Any

from packages.evaluation_engine.models import (
    EvidenceStatus,
    MetricEvidence,
    MetricResult,
    MetricType,
)


def validate_k(k: int) -> None:
    if k < 1:
        raise ValueError("k must be at least 1")


def build_result(
    name: str,
    metric_type: MetricType,
    value: float,
    observed: dict[str, Any],
    *,
    passed: bool | None = None,
    explanation: str | None = None,
) -> MetricResult:
    return MetricResult(
        metric_name=name,
        metric_type=metric_type,
        value=value,
        passed=passed,
        evidence=MetricEvidence(
            status=EvidenceStatus.AVAILABLE,
            observed=observed,
            explanation=explanation,
        ),
        explanation=explanation,
    )


def unknown_result(
    name: str,
    metric_type: MetricType,
    reason: str,
    observed: dict[str, Any] | None = None,
) -> MetricResult:
    return MetricResult(
        metric_name=name,
        metric_type=metric_type,
        value=None,
        passed=None,
        evidence=MetricEvidence(
            status=EvidenceStatus.UNKNOWN,
            observed=observed or {},
            explanation=reason,
        ),
        explanation=reason,
    )


def minimum_passed(value: float, threshold: float | None) -> bool | None:
    return None if threshold is None else value >= threshold


def maximum_passed(value: float, threshold: float | None) -> bool | None:
    return None if threshold is None else value <= threshold

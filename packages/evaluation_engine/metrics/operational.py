from __future__ import annotations

from packages.evaluation_engine.metrics.common import (
    build_result,
    maximum_passed,
    unknown_result,
)
from packages.evaluation_engine.models import MetricResult, MetricType


def latency_metric(
    latency_ms: float | None,
    *,
    maximum_ms: float | None = None,
) -> MetricResult:
    if latency_ms is None:
        return unknown_result(
            "latency_ms",
            MetricType.OPERATIONAL,
            "Latency evidence was unavailable",
        )
    if latency_ms < 0:
        raise ValueError("latency_ms cannot be negative")
    return build_result(
        "latency_ms",
        MetricType.OPERATIONAL,
        latency_ms,
        {"latency_ms": latency_ms, "maximum_ms": maximum_ms},
        passed=maximum_passed(latency_ms, maximum_ms),
    )


def error_rate_metric(
    error_count: int,
    total_requests: int,
    *,
    maximum_rate: float | None = None,
) -> MetricResult:
    if error_count < 0:
        raise ValueError("error_count cannot be negative")
    if total_requests < 0:
        raise ValueError("total_requests cannot be negative")
    if error_count > total_requests:
        raise ValueError("error_count cannot exceed total_requests")
    if total_requests == 0:
        return unknown_result(
            "error_rate",
            MetricType.OPERATIONAL,
            "Error rate is undefined without executed requests",
        )
    value = error_count / total_requests
    return build_result(
        "error_rate",
        MetricType.OPERATIONAL,
        value,
        {"error_count": error_count, "total_requests": total_requests},
        passed=maximum_passed(value, maximum_rate),
    )

import pytest

from packages.evaluation_engine.metrics import error_rate_metric, latency_metric
from packages.evaluation_engine.models import EvidenceStatus


def test_latency_metric_passes_threshold() -> None:
    result = latency_metric(125.0, maximum_ms=500.0)
    assert result.value == 125.0
    assert result.passed is True


def test_latency_metric_fails_threshold() -> None:
    result = latency_metric(750.0, maximum_ms=500.0)
    assert result.passed is False


def test_missing_latency_is_unknown() -> None:
    result = latency_metric(None, maximum_ms=500.0)
    assert result.value is None
    assert result.evidence.status == EvidenceStatus.UNKNOWN


def test_negative_latency_is_rejected() -> None:
    with pytest.raises(ValueError, match="negative"):
        latency_metric(-1.0)


def test_error_rate_matches_hand_calculation() -> None:
    result = error_rate_metric(2, 100, maximum_rate=0.01)
    assert result.value == 0.02
    assert result.passed is False


def test_zero_error_rate_passes() -> None:
    result = error_rate_metric(0, 20, maximum_rate=0.01)
    assert result.value == 0.0
    assert result.passed is True


def test_error_rate_is_unknown_without_requests() -> None:
    result = error_rate_metric(0, 0)
    assert result.value is None
    assert result.evidence.status == EvidenceStatus.UNKNOWN


def test_impossible_error_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        error_rate_metric(2, 1)

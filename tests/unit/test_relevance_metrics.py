import math

import pytest

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
from packages.evaluation_engine.models import EvidenceStatus

ACTUAL = ["A", "X", "B", "Y"]
RELEVANT = {"A", "B", "C"}


def test_precision_at_k_matches_hand_calculation() -> None:
    result = precision_at_k(ACTUAL, RELEVANT, 4)
    assert result.value == 2 / 4
    assert result.evidence.observed["relevant_hits"] == ["A", "B"]


def test_recall_at_k_matches_hand_calculation() -> None:
    result = recall_at_k(ACTUAL, RELEVANT, 4)
    assert result.value == 2 / 3
    assert result.evidence.observed["missed_relevant"] == ["C"]


def test_false_positive_rate_matches_hand_calculation() -> None:
    result = false_positive_rate(ACTUAL, RELEVANT)
    assert result.value == 2 / 4
    assert result.evidence.observed["false_positives"] == ["X", "Y"]


def test_false_negative_rate_matches_hand_calculation() -> None:
    result = false_negative_rate(ACTUAL, RELEVANT)
    assert result.value == 1 / 3
    assert result.evidence.observed["false_negatives"] == ["C"]


def test_reciprocal_rank_matches_hand_calculation() -> None:
    result = reciprocal_rank(["X", "B", "A"], RELEVANT)
    assert result.value == 1 / 2
    assert result.evidence.observed["first_relevant_rank"] == 2


def test_reciprocal_rank_is_zero_when_no_relevant_result_is_returned() -> None:
    assert reciprocal_rank(["X", "Y"], RELEVANT).value == 0.0


def test_mrr_matches_hand_calculation() -> None:
    result = mean_reciprocal_rank([1.0, 0.5, 0.0])
    assert result.value == 0.5


def test_ndcg_matches_hand_calculation() -> None:
    result = ndcg_at_k(["B", "C", "A"], {"A": 3, "B": 2, "C": 1}, 3)
    hand_dcg = 3 + (1 / math.log2(3)) + (7 / 2)
    hand_ideal_dcg = 7 + (3 / math.log2(3)) + (1 / 2)
    assert result.value == pytest.approx(hand_dcg / hand_ideal_dcg)


def test_ndcg_handles_tied_relevance_grades() -> None:
    result = ndcg_at_k(["B", "A"], {"A": 2, "B": 2}, 2)
    assert result.value == pytest.approx(1.0)


def test_top_result_correctness() -> None:
    assert top_result_correctness(["A", "X"], RELEVANT).value == 1.0
    assert top_result_correctness(["X", "A"], RELEVANT).value == 0.0
    assert top_result_correctness([], RELEVANT).value == 0.0


def test_relevant_result_displacement_matches_hand_calculation() -> None:
    result = relevant_result_displacement(["B", "A", "C"], ["A", "B", "C"])
    assert result.value == 1 / 3
    assert result.evidence.observed["displacements"] == {"A": 1, "B": 0, "C": 0}


def test_missing_relevant_result_has_explicit_displacement() -> None:
    result = relevant_result_displacement(["A"], ["A", "B"])
    assert result.value == 1 / 2
    assert result.evidence.observed["missing_rank"] == 3


def test_missing_labels_return_unknown_instead_of_silent_zero() -> None:
    results = [
        recall_at_k(["A"], set(), 10),
        false_negative_rate(["A"], set()),
        reciprocal_rank(["A"], set()),
        ndcg_at_k(["A"], {}, 10),
        top_result_correctness(["A"], set()),
        relevant_result_displacement(["A"], []),
    ]
    assert all(result.value is None for result in results)
    assert all(result.evidence.status == EvidenceStatus.UNKNOWN for result in results)


def test_empty_results_make_false_positive_rate_unknown() -> None:
    result = false_positive_rate([], RELEVANT)
    assert result.value is None
    assert result.evidence.status == EvidenceStatus.UNKNOWN


def test_invalid_k_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        precision_at_k(ACTUAL, RELEVANT, 0)

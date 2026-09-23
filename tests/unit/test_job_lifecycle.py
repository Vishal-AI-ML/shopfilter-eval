from services.api.shopfilter_api.job_lifecycle import (
    TERMINAL_JOB_STATUSES,
    EvaluationJobStatus,
    can_transition,
)


def test_job_lifecycle_allows_documented_transitions() -> None:
    assert can_transition(EvaluationJobStatus.QUEUED, EvaluationJobStatus.RUNNING)
    assert can_transition(EvaluationJobStatus.QUEUED, EvaluationJobStatus.CANCELLED)
    assert can_transition(EvaluationJobStatus.RUNNING, EvaluationJobStatus.COMPLETED)
    assert can_transition(
        EvaluationJobStatus.RUNNING, EvaluationJobStatus.COMPLETED_WITH_ERRORS
    )
    assert can_transition(EvaluationJobStatus.RUNNING, EvaluationJobStatus.FAILED)


def test_terminal_job_states_cannot_transition() -> None:
    for current in TERMINAL_JOB_STATUSES:
        for target in EvaluationJobStatus:
            assert not can_transition(current, target)

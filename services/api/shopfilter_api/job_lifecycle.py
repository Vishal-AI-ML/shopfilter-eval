from __future__ import annotations

from enum import StrEnum


class EvaluationJobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL_JOB_STATUSES = {
    EvaluationJobStatus.COMPLETED,
    EvaluationJobStatus.COMPLETED_WITH_ERRORS,
    EvaluationJobStatus.FAILED,
    EvaluationJobStatus.CANCELLED,
}

_ALLOWED_TRANSITIONS = {
    EvaluationJobStatus.QUEUED: {
        EvaluationJobStatus.RUNNING,
        EvaluationJobStatus.CANCELLED,
        EvaluationJobStatus.FAILED,
    },
    EvaluationJobStatus.RUNNING: {
        EvaluationJobStatus.COMPLETED,
        EvaluationJobStatus.COMPLETED_WITH_ERRORS,
        EvaluationJobStatus.FAILED,
        EvaluationJobStatus.CANCELLED,
    },
}


def can_transition(current: EvaluationJobStatus, target: EvaluationJobStatus) -> bool:
    return target in _ALLOWED_TRANSITIONS.get(current, set())

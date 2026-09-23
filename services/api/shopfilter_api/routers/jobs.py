from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.shopfilter_api.dependencies import (
    OrganizationContext,
    ResourceWriter,
    get_session,
)
from services.api.shopfilter_api.job_lifecycle import (
    TERMINAL_JOB_STATUSES,
    EvaluationJobStatus,
)
from services.api.shopfilter_api.job_queue import JobQueue, JobQueueUnavailable
from services.api.shopfilter_api.job_schemas import (
    EvaluationJobCreate,
    EvaluationJobResponse,
)
from services.api.shopfilter_api.models import (
    DatasetRecord,
    DatasetVersionRecord,
    EvaluationJobRecord,
    SearchSystemRecord,
    SearchSystemVersionRecord,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/evaluation-jobs", tags=["evaluation jobs"])
DbSession = Annotated[Session, Depends(get_session)]


def _queue(request: Request) -> JobQueue:
    return request.app.state.job_queue


JobQueueDependency = Annotated[JobQueue, Depends(_queue)]


def _require_inputs(
    session: Session,
    organization_id: uuid.UUID,
    body: EvaluationJobCreate,
) -> DatasetVersionRecord:
    dataset_version = session.scalar(
        select(DatasetVersionRecord)
        .join(DatasetRecord)
        .where(
            DatasetVersionRecord.id == body.dataset_version_id,
            DatasetVersionRecord.organization_id == organization_id,
            DatasetRecord.organization_id == organization_id,
            DatasetRecord.project_id == body.project_id,
        )
    )
    if dataset_version is None:
        raise HTTPException(status_code=404, detail="Dataset version not found")
    search_version = session.scalar(
        select(SearchSystemVersionRecord)
        .join(SearchSystemRecord)
        .where(
            SearchSystemVersionRecord.id == body.search_system_version_id,
            SearchSystemVersionRecord.organization_id == organization_id,
            SearchSystemRecord.organization_id == organization_id,
            SearchSystemRecord.project_id == body.project_id,
        )
    )
    if search_version is None:
        raise HTTPException(status_code=404, detail="Search system version not found")
    return dataset_version


def _same_request(job: EvaluationJobRecord, body: EvaluationJobCreate) -> bool:
    return (
        job.project_id == body.project_id
        and job.dataset_version_id == body.dataset_version_id
        and job.search_system_version_id == body.search_system_version_id
        and job.top_k == body.top_k
        and job.seed == body.seed
        and job.max_attempts == body.max_attempts
    )


def _dispatch(
    session: Session, queue: JobQueue, job: EvaluationJobRecord
) -> None:
    if job.dispatched_at is not None or job.status != EvaluationJobStatus.QUEUED.value:
        return
    try:
        queue.enqueue(job.id)
    except JobQueueUnavailable:
        logger.warning("Evaluation job dispatch deferred", extra={"job_id": str(job.id)})
        return
    job.dispatched_at = datetime.now(UTC)
    session.commit()
    session.refresh(job)


@router.post("", response_model=EvaluationJobResponse, status_code=status.HTTP_202_ACCEPTED)
def create_evaluation_job(
    body: EvaluationJobCreate,
    writer: ResourceWriter,
    session: DbSession,
    queue: JobQueueDependency,
) -> EvaluationJobRecord:
    existing = session.scalar(
        select(EvaluationJobRecord).where(
            EvaluationJobRecord.organization_id == writer.organization_id,
            EvaluationJobRecord.idempotency_key == body.idempotency_key,
        )
    )
    if existing is not None:
        if not _same_request(existing, body):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key already belongs to a different request",
            )
        _dispatch(session, queue, existing)
        return existing

    dataset_version = _require_inputs(session, writer.organization_id, body)
    job = EvaluationJobRecord(
        organization_id=writer.organization_id,
        project_id=body.project_id,
        dataset_version_id=body.dataset_version_id,
        search_system_version_id=body.search_system_version_id,
        requested_by_user_id=writer.user.id,
        idempotency_key=body.idempotency_key,
        status=EvaluationJobStatus.QUEUED.value,
        completed_case_count=0,
        total_case_count=dataset_version.item_count,
        attempt_count=0,
        max_attempts=body.max_attempts,
        top_k=body.top_k,
        seed=body.seed,
        cancel_requested=False,
    )
    session.add(job)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        concurrent = session.scalar(
            select(EvaluationJobRecord).where(
                EvaluationJobRecord.organization_id == writer.organization_id,
                EvaluationJobRecord.idempotency_key == body.idempotency_key,
            )
        )
        if concurrent is None:
            raise
        if not _same_request(concurrent, body):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key already belongs to a different request",
            ) from None
        _dispatch(session, queue, concurrent)
        return concurrent
    session.refresh(job)
    _dispatch(session, queue, job)
    return job


@router.get("", response_model=list[EvaluationJobResponse])
def list_evaluation_jobs(
    access: OrganizationContext, session: DbSession
) -> list[EvaluationJobRecord]:
    return list(
        session.scalars(
            select(EvaluationJobRecord)
            .where(EvaluationJobRecord.organization_id == access.organization_id)
            .order_by(EvaluationJobRecord.created_at.desc())
        ).all()
    )


@router.get("/{job_id}", response_model=EvaluationJobResponse)
def get_evaluation_job(
    job_id: uuid.UUID,
    access: OrganizationContext,
    session: DbSession,
) -> EvaluationJobRecord:
    job = session.scalar(
        select(EvaluationJobRecord).where(
            EvaluationJobRecord.id == job_id,
            EvaluationJobRecord.organization_id == access.organization_id,
        )
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Evaluation job not found")
    return job


@router.post("/{job_id}/cancel", response_model=EvaluationJobResponse)
def cancel_evaluation_job(
    job_id: uuid.UUID,
    writer: ResourceWriter,
    session: DbSession,
) -> EvaluationJobRecord:
    job = session.scalar(
        select(EvaluationJobRecord)
        .where(
            EvaluationJobRecord.id == job_id,
            EvaluationJobRecord.organization_id == writer.organization_id,
        )
        .with_for_update()
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Evaluation job not found")
    current = EvaluationJobStatus(job.status)
    if current in TERMINAL_JOB_STATUSES:
        raise HTTPException(status_code=409, detail="Evaluation job is already terminal")
    job.cancel_requested = True
    if current is EvaluationJobStatus.QUEUED:
        job.status = EvaluationJobStatus.CANCELLED.value
        job.finished_at = datetime.now(UTC)
    session.commit()
    session.refresh(job)
    return job

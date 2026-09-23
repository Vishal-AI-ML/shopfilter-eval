
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.shopfilter_api.dependencies import get_organization_id, get_session
from services.api.shopfilter_api.models import (
    CaseResultRecord,
    EvaluationRunRecord,
    FailureRecord,
    MetricResultRecord,
    Project,
    SearchSystemRecord,
    SearchSystemVersionRecord,
)
from services.api.shopfilter_api.schemas import (
    EvaluationRunDetailResponse,
    EvaluationRunResponse,
    SearchSystemCreate,
    SearchSystemResponse,
    SearchSystemVersionCreate,
    SearchSystemVersionResponse,
)

router = APIRouter(prefix="/v1", tags=["search systems and evaluations"])
TenantId = Annotated[uuid.UUID, Depends(get_organization_id)]
DbSession = Annotated[Session, Depends(get_session)]


def _require_project(session: Session, organization_id: uuid.UUID, project_id: uuid.UUID) -> None:
    project = session.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == organization_id,
        )
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")


def _commit(session: Session, record: object, detail: str) -> None:
    session.add(record)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=detail) from exc


@router.post(
    "/search-systems",
    response_model=SearchSystemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_search_system(
    body: SearchSystemCreate, organization_id: TenantId, session: DbSession
) -> SearchSystemRecord:
    _require_project(session, organization_id, body.project_id)
    record = SearchSystemRecord(
        organization_id=organization_id,
        project_id=body.project_id,
        name=body.name,
        provider=body.provider.strip(),
    )
    _commit(session, record, "Search system name already exists in this project")
    session.refresh(record)
    return record


@router.get("/search-systems", response_model=list[SearchSystemResponse])
def list_search_systems(
    organization_id: TenantId, session: DbSession
) -> list[SearchSystemRecord]:
    return list(
        session.scalars(
            select(SearchSystemRecord)
            .where(SearchSystemRecord.organization_id == organization_id)
            .order_by(SearchSystemRecord.name)
        ).all()
    )


@router.post(
    "/search-systems/{search_system_id}/versions",
    response_model=SearchSystemVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_search_system_version(
    search_system_id: uuid.UUID,
    body: SearchSystemVersionCreate,
    organization_id: TenantId,
    session: DbSession,
) -> SearchSystemVersionRecord:
    system = session.scalar(
        select(SearchSystemRecord).where(
            SearchSystemRecord.id == search_system_id,
            SearchSystemRecord.organization_id == organization_id,
        )
    )
    if system is None:
        raise HTTPException(status_code=404, detail="Search system not found")
    record = SearchSystemVersionRecord(
        organization_id=organization_id,
        search_system_id=search_system_id,
        version=body.version.strip(),
        configuration=body.configuration,
    )
    _commit(session, record, "Search system version already exists")
    session.refresh(record)
    return record


@router.get(
    "/search-systems/{search_system_id}/versions",
    response_model=list[SearchSystemVersionResponse],
)
def list_search_system_versions(
    search_system_id: uuid.UUID,
    organization_id: TenantId,
    session: DbSession,
) -> list[SearchSystemVersionRecord]:
    return list(
        session.scalars(
            select(SearchSystemVersionRecord)
            .where(
                SearchSystemVersionRecord.search_system_id == search_system_id,
                SearchSystemVersionRecord.organization_id == organization_id,
            )
            .order_by(SearchSystemVersionRecord.created_at)
        ).all()
    )


@router.get("/evaluation-runs", response_model=list[EvaluationRunResponse])
def list_evaluation_runs(
    organization_id: TenantId, session: DbSession
) -> list[EvaluationRunRecord]:
    return list(
        session.scalars(
            select(EvaluationRunRecord)
            .where(EvaluationRunRecord.organization_id == organization_id)
            .order_by(EvaluationRunRecord.created_at.desc())
        ).all()
    )


@router.get("/evaluation-runs/{run_id}", response_model=EvaluationRunDetailResponse)
def get_evaluation_run(
    run_id: uuid.UUID, organization_id: TenantId, session: DbSession
) -> EvaluationRunDetailResponse:
    run = session.scalar(
        select(EvaluationRunRecord).where(
            EvaluationRunRecord.id == run_id,
            EvaluationRunRecord.organization_id == organization_id,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    metric_count = session.scalar(
        select(func.count(MetricResultRecord.id))
        .join(CaseResultRecord)
        .where(CaseResultRecord.evaluation_run_id == run.id)
    ) or 0
    failure_count = session.scalar(
        select(func.count(FailureRecord.id))
        .join(CaseResultRecord)
        .where(CaseResultRecord.evaluation_run_id == run.id)
    ) or 0
    base = EvaluationRunResponse.model_validate(run).model_dump()
    return EvaluationRunDetailResponse(
        **base,
        result_fingerprint=run.result_fingerprint,
        artifact_hash=run.artifact_hash,
        artifact_uri=run.artifact_uri,
        trace_provider=run.trace_provider,
        metric_definition_version=run.metric_definition_version,
        top_k=run.top_k,
        seed=run.seed,
        metric_result_count=metric_count,
        failure_count=failure_count,
    )

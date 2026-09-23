
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.shopfilter_api.dependencies import (
    ResourceWriter,
    get_organization_id,
    get_session,
)
from services.api.shopfilter_api.models import (
    CatalogRecord,
    CatalogVersionRecord,
    DatasetRecord,
    DatasetVersionRecord,
    Organization,
    Project,
)
from services.api.shopfilter_api.schemas import (
    CatalogCreate,
    CatalogResponse,
    CatalogVersionResponse,
    DatasetCreate,
    DatasetResponse,
    DatasetVersionResponse,
    ProjectCreate,
    ProjectResponse,
)

router = APIRouter(prefix="/v1", tags=["project resources"])
TenantId = Annotated[uuid.UUID, Depends(get_organization_id)]
DbSession = Annotated[Session, Depends(get_session)]
def _commit[RecordT: (Project, CatalogRecord, DatasetRecord)](
    session: Session, record: RecordT, conflict: str
) -> RecordT:
    session.add(record)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=conflict) from exc
    session.refresh(record)
    return record


def _require_organization(session: Session, organization_id: uuid.UUID) -> None:
    if session.get(Organization, organization_id) is None:
        raise HTTPException(status_code=404, detail="Organization not found")


def _require_project(
    session: Session,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
) -> Project:
    project = session.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == organization_id,
        )
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project



@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectCreate,
    organization_id: TenantId,
    session: DbSession,
    _writer: ResourceWriter,
) -> Project:
    _require_organization(session, organization_id)
    return _commit(
        session,
        Project(organization_id=organization_id, name=body.name, slug=body.slug),
        "Project slug already exists in this organization",
    )


@router.get("/projects", response_model=list[ProjectResponse])
def list_projects(organization_id: TenantId, session: DbSession) -> list[Project]:
    return list(
        session.scalars(
            select(Project)
            .where(Project.organization_id == organization_id)
            .order_by(Project.name)
        ).all()
    )


@router.post("/catalogs", response_model=CatalogResponse, status_code=status.HTTP_201_CREATED)
def create_catalog(
    body: CatalogCreate,
    organization_id: TenantId,
    session: DbSession,
    _writer: ResourceWriter,
) -> CatalogRecord:
    _require_project(session, organization_id, body.project_id)
    return _commit(
        session,
        CatalogRecord(organization_id=organization_id, project_id=body.project_id, name=body.name),
        "Catalog name already exists in this project",
    )


@router.get("/catalogs", response_model=list[CatalogResponse])
def list_catalogs(organization_id: TenantId, session: DbSession) -> list[CatalogRecord]:
    return list(
        session.scalars(
            select(CatalogRecord)
            .where(CatalogRecord.organization_id == organization_id)
            .order_by(CatalogRecord.name)
        ).all()
    )


@router.post("/datasets", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
def create_dataset(
    body: DatasetCreate,
    organization_id: TenantId,
    session: DbSession,
    _writer: ResourceWriter,
) -> DatasetRecord:
    _require_project(session, organization_id, body.project_id)
    return _commit(
        session,
        DatasetRecord(organization_id=organization_id, project_id=body.project_id, name=body.name),
        "Dataset name already exists in this project",
    )


@router.get("/datasets", response_model=list[DatasetResponse])
def list_datasets(organization_id: TenantId, session: DbSession) -> list[DatasetRecord]:
    return list(
        session.scalars(
            select(DatasetRecord)
            .where(DatasetRecord.organization_id == organization_id)
            .order_by(DatasetRecord.name)
        ).all()
    )


@router.get(
    "/catalogs/{catalog_id}/versions", response_model=list[CatalogVersionResponse]
)
def list_catalog_versions(
    catalog_id: uuid.UUID, organization_id: TenantId, session: DbSession
) -> list[CatalogVersionRecord]:
    catalog = session.scalar(
        select(CatalogRecord).where(
            CatalogRecord.id == catalog_id,
            CatalogRecord.organization_id == organization_id,
        )
    )
    if catalog is None:
        raise HTTPException(status_code=404, detail="Catalog not found")
    return list(
        session.scalars(
            select(CatalogVersionRecord)
            .where(
                CatalogVersionRecord.organization_id == organization_id,
                CatalogVersionRecord.catalog_id == catalog.id,
            )
            .order_by(CatalogVersionRecord.created_at)
        ).all()
    )


@router.get(
    "/catalogs/{catalog_id}/versions/{version_id}",
    response_model=CatalogVersionResponse,
)
def get_catalog_version(
    catalog_id: uuid.UUID,
    version_id: uuid.UUID,
    organization_id: TenantId,
    session: DbSession,
) -> CatalogVersionRecord:
    version = session.scalar(
        select(CatalogVersionRecord).where(
            CatalogVersionRecord.id == version_id,
            CatalogVersionRecord.catalog_id == catalog_id,
            CatalogVersionRecord.organization_id == organization_id,
        )
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Catalog version not found")
    return version


@router.get(
    "/datasets/{dataset_id}/versions", response_model=list[DatasetVersionResponse]
)
def list_dataset_versions(
    dataset_id: uuid.UUID, organization_id: TenantId, session: DbSession
) -> list[DatasetVersionRecord]:
    dataset = session.scalar(
        select(DatasetRecord).where(
            DatasetRecord.id == dataset_id,
            DatasetRecord.organization_id == organization_id,
        )
    )
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return list(
        session.scalars(
            select(DatasetVersionRecord)
            .where(
                DatasetVersionRecord.organization_id == organization_id,
                DatasetVersionRecord.dataset_id == dataset.id,
            )
            .order_by(DatasetVersionRecord.created_at)
        ).all()
    )


@router.get(
    "/datasets/{dataset_id}/versions/{version_id}",
    response_model=DatasetVersionResponse,
)
def get_dataset_version(
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    organization_id: TenantId,
    session: DbSession,
) -> DatasetVersionRecord:
    version = session.scalar(
        select(DatasetVersionRecord).where(
            DatasetVersionRecord.id == version_id,
            DatasetVersionRecord.dataset_id == dataset_id,
            DatasetVersionRecord.organization_id == organization_id,
        )
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Dataset version not found")
    return version

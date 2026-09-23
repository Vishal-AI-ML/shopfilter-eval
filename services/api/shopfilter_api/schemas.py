
from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EntityCreate(StrictSchema):
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value


class SluggedEntityCreate(EntityCreate):
    slug: str = Field(min_length=1, max_length=100)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        value = value.strip().lower()
        if not _SLUG.fullmatch(value):
            raise ValueError("slug must contain lowercase letters, numbers, and hyphens")
        return value


class OrganizationCreate(SluggedEntityCreate):
    pass


class ProjectCreate(SluggedEntityCreate):
    pass


class CatalogCreate(EntityCreate):
    project_id: uuid.UUID


class DatasetCreate(EntityCreate):
    project_id: uuid.UUID


class EntityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID | None = None
    name: str
    created_at: datetime


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime


class ProjectResponse(EntityResponse):
    organization_id: uuid.UUID
    slug: str


class CatalogResponse(EntityResponse):
    organization_id: uuid.UUID
    project_id: uuid.UUID


class DatasetResponse(EntityResponse):
    organization_id: uuid.UUID
    project_id: uuid.UUID


class SearchSystemCreate(EntityCreate):
    project_id: uuid.UUID
    provider: str = Field(min_length=1, max_length=100)


class SearchSystemVersionCreate(StrictSchema):
    version: str = Field(min_length=1, max_length=200)
    configuration: dict[str, object] = Field(default_factory=dict)


class SearchSystemResponse(EntityResponse):
    organization_id: uuid.UUID
    project_id: uuid.UUID
    provider: str


class SearchSystemVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    search_system_id: uuid.UUID
    version: str
    configuration: dict[str, object]
    created_at: datetime


class EvaluationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    external_run_id: str
    status: str
    dataset_id: str
    dataset_version: str
    catalog_id: str
    catalog_version: str
    adapter_provider: str
    case_count: int
    passed_case_count: int
    failed_case_count: int
    aggregate_metrics: dict[str, object]
    failure_counts: dict[str, object]
    created_at: datetime


class EvaluationRunDetailResponse(EvaluationRunResponse):
    result_fingerprint: str
    artifact_hash: str
    artifact_uri: str | None
    trace_provider: str
    metric_definition_version: str
    top_k: int
    seed: int
    metric_result_count: int
    failure_count: int

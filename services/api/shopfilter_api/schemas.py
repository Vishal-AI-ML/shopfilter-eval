
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

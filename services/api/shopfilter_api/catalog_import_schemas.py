from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class CatalogImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: uuid.UUID
    artifact: dict[str, object]


class CatalogImportResponse(BaseModel):
    resource_id: uuid.UUID
    version_id: uuid.UUID
    external_id: str
    version: str
    created: bool
    item_count: int
    content_hash: str
    artifact_hash: str

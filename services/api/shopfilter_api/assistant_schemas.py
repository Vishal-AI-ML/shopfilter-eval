from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AssistantPlaygroundRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: uuid.UUID
    catalog_version_id: uuid.UUID
    ai_system_version_id: uuid.UUID
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query cannot be blank")
        return value


class AssistantCitation(BaseModel):
    claim: str
    source_id: str
    source_version: str


class AssistantProductEvidence(BaseModel):
    product_id: str
    title: str
    description: str | None
    category: str
    brand: str | None
    color: str | None
    price: str | None
    currency: str
    availability: str
    rank: int
    score: float
    score_breakdown: dict[str, float]
    citation: AssistantCitation


class AssistantSystemSummary(BaseModel):
    id: uuid.UUID
    version_id: uuid.UUID
    name: str
    version: str
    system_type: str
    provider: str
    capabilities: dict[str, Any]
    content_hash: str


class AssistantCatalogSummary(BaseModel):
    id: uuid.UUID
    version_id: uuid.UUID
    name: str
    external_id: str | None
    version: str
    content_hash: str | None


class AssistantPlaygroundResponse(BaseModel):
    answer: str
    mode: Literal["DETERMINISTIC_REFERENCE"]
    generation_provider: Literal["DISABLED"]
    system: AssistantSystemSummary
    catalog: AssistantCatalogSummary
    interpreted_query: dict[str, Any] | None
    applied_filters: dict[str, Any] | None
    retrieved_candidate_ids: list[str]
    filtered_candidate_ids: list[str]
    products: list[AssistantProductEvidence]
    citations: list[AssistantCitation]
    missing_information: list[str]
    latency_ms: float

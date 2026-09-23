from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from services.api.shopfilter_api.job_lifecycle import EvaluationJobStatus


class EvaluationJobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: uuid.UUID
    dataset_version_id: uuid.UUID
    search_system_version_id: uuid.UUID
    idempotency_key: str = Field(min_length=1, max_length=200)
    top_k: int = Field(default=10, ge=1, le=100)
    seed: int = Field(default=42, ge=0)
    max_attempts: int = Field(default=3, ge=1, le=10)


class EvaluationJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    dataset_version_id: uuid.UUID
    search_system_version_id: uuid.UUID
    requested_by_user_id: uuid.UUID
    evaluation_run_id: uuid.UUID | None
    idempotency_key: str
    status: EvaluationJobStatus
    completed_case_count: int
    total_case_count: int
    attempt_count: int
    max_attempts: int
    cancel_requested: bool
    dispatched_at: datetime | None
    started_at: datetime | None
    heartbeat_at: datetime | None
    finished_at: datetime | None
    error_code: str | None
    error_detail: str | None
    created_at: datetime
    updated_at: datetime

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ReviewDecision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class DatasetReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ReviewDecision
    note: str | None = Field(default=None, max_length=2000)


class DatasetReviewResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    dataset_version_id: uuid.UUID
    reviewer_user_id: uuid.UUID
    reviewer_display_name: str
    decision: ReviewDecision
    note: str | None
    created_at: datetime

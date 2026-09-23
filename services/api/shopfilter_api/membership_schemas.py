from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from services.api.shopfilter_api.auth import MembershipRole

_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class MembershipCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    role: MembershipRole

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if not _EMAIL.fullmatch(normalized):
            raise ValueError("email must be valid")
        return normalized


class MembershipUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: MembershipRole


class OrganizationMemberResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    display_name: str
    role: MembershipRole
    created_at: datetime

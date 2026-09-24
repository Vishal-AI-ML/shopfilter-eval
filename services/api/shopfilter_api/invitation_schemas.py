from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from services.api.shopfilter_api.auth import MembershipRole

_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class InvitationCreate(BaseModel):
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


class InvitationResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    email: str
    role: MembershipRole
    expires_at: datetime
    created_at: datetime


class InvitationAcceptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=32, max_length=512)
    display_name: str | None = Field(default=None, max_length=200)
    password: str = Field(min_length=12, max_length=1024)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

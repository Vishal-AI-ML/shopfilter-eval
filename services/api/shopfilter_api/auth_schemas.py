from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().casefold()
        if not _EMAIL.fullmatch(value):
            raise ValueError("email must be valid")
        return value


class MembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    organization_id: uuid.UUID
    role: str


class AuthenticatedUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_active: bool
    memberships: list[MembershipResponse]


class LoginResponse(BaseModel):
    user: AuthenticatedUserResponse
    expires_at: datetime

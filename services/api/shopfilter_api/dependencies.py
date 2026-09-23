
from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import Header, HTTPException, Request, status
from sqlalchemy.orm import Session


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.database.session() as session:
        yield session


def get_organization_id(
    x_organization_id: Annotated[str | None, Header()] = None,
) -> uuid.UUID:
    if x_organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Organization-ID header is required",
        )
    try:
        return uuid.UUID(x_organization_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Organization-ID must be a valid UUID",
        ) from exc

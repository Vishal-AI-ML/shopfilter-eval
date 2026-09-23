
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.api.shopfilter_api.dependencies import get_session

router = APIRouter(prefix="/health", tags=["health"])
DbSession = Annotated[Session, Depends(get_session)]


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(session: DbSession) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ready"}

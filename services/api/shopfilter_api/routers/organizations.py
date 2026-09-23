
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.shopfilter_api.dependencies import get_session
from services.api.shopfilter_api.models import Organization
from services.api.shopfilter_api.schemas import OrganizationCreate, OrganizationResponse

router = APIRouter(prefix="/v1/organizations", tags=["organizations"])
DbSession = Annotated[Session, Depends(get_session)]


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    body: OrganizationCreate,
    session: DbSession,
) -> Organization:
    organization = Organization(name=body.name, slug=body.slug)
    session.add(organization)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Organization slug already exists") from exc
    session.refresh(organization)
    return organization


@router.get("/{slug}", response_model=OrganizationResponse)
def get_organization(slug: str, session: DbSession) -> Organization:
    organization = session.scalar(select(Organization).where(Organization.slug == slug))
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization

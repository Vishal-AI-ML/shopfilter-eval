from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.shopfilter_api.auth import MembershipRole
from services.api.shopfilter_api.dependencies import CurrentUser, get_session
from services.api.shopfilter_api.models import (
    MembershipRecord,
    Organization,
    UserRecord,
)
from services.api.shopfilter_api.schemas import OrganizationCreate, OrganizationResponse

router = APIRouter(prefix="/v1/organizations", tags=["organizations"])
DbSession = Annotated[Session, Depends(get_session)]


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    body: OrganizationCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> Organization:
    if current_user.email_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verified email required to create an organization",
        )
    organization = Organization(name=body.name, slug=body.slug)
    session.add(organization)
    try:
        session.flush()
        session.add(
            MembershipRecord(
                organization_id=organization.id,
                user_id=current_user.id,
                role=MembershipRole.OWNER.value,
            )
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Organization slug already exists") from exc
    session.refresh(organization)
    return organization


@router.get("/{slug}", response_model=OrganizationResponse)
def get_organization(
    slug: str, current_user: CurrentUser, session: DbSession
) -> Organization:
    organization = session.scalar(
        select(Organization)
        .join(MembershipRecord)
        .join(UserRecord)
        .where(
            Organization.slug == slug,
            MembershipRecord.user_id == current_user.id,
            UserRecord.is_active.is_(True),
        )
    )
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization

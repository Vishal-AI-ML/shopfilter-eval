from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.shopfilter_api.auth import MembershipRole
from services.api.shopfilter_api.dependencies import OrganizationContext, get_session
from services.api.shopfilter_api.membership_schemas import (
    MembershipCreate,
    MembershipUpdate,
    OrganizationMemberResponse,
)
from services.api.shopfilter_api.models import MembershipRecord, UserRecord

router = APIRouter(prefix="/v1/organization-members", tags=["organization members"])
DbSession = Annotated[Session, Depends(get_session)]


def _require_manager(access: OrganizationContext) -> None:
    if access.user.email_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verified email required for membership management",
        )
    if access.role not in {MembershipRole.OWNER, MembershipRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role for membership management",
        )


def _response(membership: MembershipRecord, user: UserRecord) -> OrganizationMemberResponse:
    return OrganizationMemberResponse(
        id=membership.id,
        organization_id=membership.organization_id,
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=MembershipRole(membership.role),
        created_at=membership.created_at,
    )


def _target(
    session: Session, organization_id: uuid.UUID, membership_id: uuid.UUID
) -> tuple[MembershipRecord, UserRecord]:
    row = session.execute(
        select(MembershipRecord, UserRecord)
        .join(UserRecord)
        .where(
            MembershipRecord.id == membership_id,
            MembershipRecord.organization_id == organization_id,
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    membership, user = row
    return membership, user


def _lock_and_protect_last_owner(session: Session, membership: MembershipRecord) -> None:
    list(
        session.scalars(
            select(MembershipRecord.id)
            .where(MembershipRecord.organization_id == membership.organization_id)
            .with_for_update()
        )
    )
    owner_count = session.scalar(
        select(func.count(MembershipRecord.id)).where(
            MembershipRecord.organization_id == membership.organization_id,
            MembershipRecord.role == MembershipRole.OWNER.value,
        )
    )
    if owner_count is None or owner_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization must retain at least one Owner",
        )


def _authorize_change(
    access: OrganizationContext,
    target: MembershipRecord,
    requested_role: MembershipRole | None,
) -> None:
    if access.role is MembershipRole.ADMIN and (
        target.role == MembershipRole.OWNER.value
        or requested_role is MembershipRole.OWNER
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an Owner can manage Owner memberships",
        )


@router.get("", response_model=list[OrganizationMemberResponse])
def list_members(
    access: OrganizationContext, session: DbSession
) -> list[OrganizationMemberResponse]:
    _require_manager(access)
    rows = session.execute(
        select(MembershipRecord, UserRecord)
        .join(UserRecord)
        .where(MembershipRecord.organization_id == access.organization_id)
        .order_by(UserRecord.email)
    ).all()
    return [_response(membership, user) for membership, user in rows]


@router.post(
    "", response_model=OrganizationMemberResponse, status_code=status.HTTP_201_CREATED
)
def add_member(
    body: MembershipCreate,
    access: OrganizationContext,
    session: DbSession,
) -> OrganizationMemberResponse:
    _require_manager(access)
    if access.role is MembershipRole.ADMIN and body.role is MembershipRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an Owner can manage Owner memberships",
        )
    user = session.scalar(
        select(UserRecord).where(
            UserRecord.email == body.email,
            UserRecord.is_active.is_(True),
        )
    )
    if user is None:
        raise HTTPException(status_code=404, detail="Unable to add membership")
    membership = MembershipRecord(
        organization_id=access.organization_id,
        user_id=user.id,
        role=body.role.value,
    )
    session.add(membership)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Membership already exists") from exc
    session.refresh(membership)
    return _response(membership, user)


@router.patch("/{membership_id}", response_model=OrganizationMemberResponse)
def change_member_role(
    membership_id: uuid.UUID,
    body: MembershipUpdate,
    access: OrganizationContext,
    session: DbSession,
) -> OrganizationMemberResponse:
    _require_manager(access)
    membership, user = _target(session, access.organization_id, membership_id)
    _authorize_change(access, membership, body.role)
    if membership.role == body.role.value:
        return _response(membership, user)
    if membership.role == MembershipRole.OWNER.value:
        _lock_and_protect_last_owner(session, membership)
    membership.role = body.role.value
    session.commit()
    session.refresh(membership)
    return _response(membership, user)


@router.delete("/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    membership_id: uuid.UUID,
    access: OrganizationContext,
    session: DbSession,
) -> Response:
    _require_manager(access)
    membership, _user = _target(session, access.organization_id, membership_id)
    _authorize_change(access, membership, None)
    if membership.role == MembershipRole.OWNER.value:
        _lock_and_protect_last_owner(session, membership)
    session.delete(membership)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

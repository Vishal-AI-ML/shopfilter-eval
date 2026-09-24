from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from services.api.shopfilter_api.auth import MembershipRole, invitation_token_hash
from services.api.shopfilter_api.dependencies import OrganizationContext, get_session
from services.api.shopfilter_api.invitation_mailer import InvitationDeliveryError
from services.api.shopfilter_api.invitation_schemas import (
    InvitationCreate,
    InvitationResponse,
)
from services.api.shopfilter_api.models import (
    MembershipRecord,
    OrganizationInvitationRecord,
    UserRecord,
)

router = APIRouter(prefix="/v1/organization-invitations", tags=["organization invitations"])
DbSession = Annotated[Session, Depends(get_session)]


def _require_inviter(access: OrganizationContext, role: MembershipRole | None = None) -> None:
    if access.user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Verified email required for invitations")
    if access.role not in {MembershipRole.OWNER, MembershipRole.ADMIN}:
        raise HTTPException(status_code=403, detail="Insufficient role for invitations")
    if access.role is MembershipRole.ADMIN and role is MembershipRole.OWNER:
        raise HTTPException(status_code=403, detail="Only an Owner can invite an Owner")


def _response(record: OrganizationInvitationRecord) -> InvitationResponse:
    return InvitationResponse(id=record.id, organization_id=record.organization_id, email=record.email, role=MembershipRole(record.role), expires_at=record.expires_at, created_at=record.created_at)


@router.get("", response_model=list[InvitationResponse])
def list_invitations(access: OrganizationContext, session: DbSession) -> list[InvitationResponse]:
    _require_inviter(access)
    now = datetime.now(UTC)
    records = session.scalars(select(OrganizationInvitationRecord).where(OrganizationInvitationRecord.organization_id == access.organization_id, OrganizationInvitationRecord.accepted_at.is_(None), OrganizationInvitationRecord.revoked_at.is_(None), OrganizationInvitationRecord.expires_at > now).order_by(OrganizationInvitationRecord.created_at.desc())).all()
    return [_response(record) for record in records]


@router.post("", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
def create_invitation(body: InvitationCreate, request: Request, access: OrganizationContext, session: DbSession) -> InvitationResponse:
    _require_inviter(access, body.role)
    existing_user = session.scalar(select(UserRecord).where(UserRecord.email == body.email))
    if existing_user is not None and (
        not existing_user.is_active
        or session.scalar(
            select(MembershipRecord.id).where(
                MembershipRecord.organization_id == access.organization_id,
                MembershipRecord.user_id == existing_user.id,
            )
        )
        is not None
    ):
        raise HTTPException(status_code=409, detail="Unable to create invitation")
    now = datetime.now(UTC)
    session.execute(update(OrganizationInvitationRecord).where(OrganizationInvitationRecord.organization_id == access.organization_id, OrganizationInvitationRecord.email == body.email, OrganizationInvitationRecord.accepted_at.is_(None), OrganizationInvitationRecord.revoked_at.is_(None)).values(revoked_at=now))
    raw_token = secrets.token_urlsafe(32)
    record = OrganizationInvitationRecord(organization_id=access.organization_id, email=body.email, role=body.role.value, invited_by_user_id=access.user.id, token_hash=invitation_token_hash(raw_token), expires_at=now + timedelta(hours=request.app.state.settings.invitation_expiry_hours))
    session.add(record)
    session.commit()
    session.refresh(record)
    url = f"{request.app.state.settings.public_web_url.rstrip('/')}/accept-invitation?token={quote(raw_token)}"
    try:
        request.app.state.invitation_mailer.send(recipient=record.email, organization_name=access.membership.organization.name, role=record.role, invitation_url=url)
    except InvitationDeliveryError as exc:
        record.revoked_at = datetime.now(UTC)
        session.commit()
        raise HTTPException(status_code=503, detail="Unable to deliver invitation") from exc
    return _response(record)


@router.delete("/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(invitation_id: uuid.UUID, access: OrganizationContext, session: DbSession) -> Response:
    _require_inviter(access)
    record = session.scalar(select(OrganizationInvitationRecord).where(OrganizationInvitationRecord.id == invitation_id, OrganizationInvitationRecord.organization_id == access.organization_id, OrganizationInvitationRecord.accepted_at.is_(None), OrganizationInvitationRecord.revoked_at.is_(None)))
    if record is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    _require_inviter(access, MembershipRole(record.role))
    record.revoked_at = datetime.now(UTC)
    session.commit()
    return Response(status_code=204)

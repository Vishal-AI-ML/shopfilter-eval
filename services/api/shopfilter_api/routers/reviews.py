from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.shopfilter_api.auth import MembershipRole
from services.api.shopfilter_api.dependencies import OrganizationContext, get_session
from services.api.shopfilter_api.models import (
    DatasetRecord,
    DatasetReviewRecord,
    DatasetVersionRecord,
    UserRecord,
)
from services.api.shopfilter_api.review_schemas import (
    DatasetReviewCreate,
    DatasetReviewResponse,
    ReviewDecision,
)

router = APIRouter(prefix="/v1/datasets", tags=["dataset reviews"])
DbSession = Annotated[Session, Depends(get_session)]


def _require_reviewer(access: OrganizationContext) -> None:
    if access.role not in {
        MembershipRole.OWNER,
        MembershipRole.ADMIN,
        MembershipRole.REVIEWER,
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role for dataset review",
        )


def _version(
    session: Session,
    organization_id: uuid.UUID,
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
) -> DatasetVersionRecord:
    version = session.scalar(
        select(DatasetVersionRecord)
        .join(DatasetRecord)
        .where(
            DatasetVersionRecord.id == version_id,
            DatasetVersionRecord.dataset_id == dataset_id,
            DatasetVersionRecord.organization_id == organization_id,
            DatasetRecord.organization_id == organization_id,
        )
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Dataset version not found")
    return version


def _response(
    review: DatasetReviewRecord, reviewer: UserRecord
) -> DatasetReviewResponse:
    return DatasetReviewResponse(
        id=review.id,
        organization_id=review.organization_id,
        dataset_version_id=review.dataset_version_id,
        reviewer_user_id=review.reviewer_user_id,
        reviewer_display_name=reviewer.display_name,
        decision=ReviewDecision(review.decision),
        note=review.note,
        created_at=review.created_at,
    )


@router.get(
    "/{dataset_id}/versions/{version_id}/reviews",
    response_model=list[DatasetReviewResponse],
)
def list_reviews(
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    access: OrganizationContext,
    session: DbSession,
) -> list[DatasetReviewResponse]:
    _version(session, access.organization_id, dataset_id, version_id)
    rows = session.execute(
        select(DatasetReviewRecord, UserRecord)
        .join(UserRecord, UserRecord.id == DatasetReviewRecord.reviewer_user_id)
        .where(
            DatasetReviewRecord.organization_id == access.organization_id,
            DatasetReviewRecord.dataset_version_id == version_id,
        )
        .order_by(DatasetReviewRecord.created_at, DatasetReviewRecord.id)
    ).all()
    return [_response(review, reviewer) for review, reviewer in rows]


@router.post(
    "/{dataset_id}/versions/{version_id}/reviews",
    response_model=DatasetReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_review(
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    body: DatasetReviewCreate,
    access: OrganizationContext,
    session: DbSession,
) -> DatasetReviewResponse:
    _require_reviewer(access)
    _version(session, access.organization_id, dataset_id, version_id)
    note = body.note.strip() if body.note is not None else None
    review = DatasetReviewRecord(
        organization_id=access.organization_id,
        dataset_version_id=version_id,
        reviewer_user_id=access.user.id,
        decision=body.decision.value,
        note=note or None,
    )
    session.add(review)
    session.commit()
    session.refresh(review)
    return _response(review, access.user)

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.api.shopfilter_api.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)

    projects: Mapped[list[Project]] = relationship(back_populates="organization")
    memberships: Mapped[list[MembershipRecord]] = relationship(
        back_populates="organization"
    )
    invitations: Mapped[list[OrganizationInvitationRecord]] = relationship(
        back_populates="organization"
    )


class UserRecord(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("email = lower(email)", name="email_normalized"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    memberships: Mapped[list[MembershipRecord]] = relationship(back_populates="user")
    sessions: Mapped[list[AuthSessionRecord]] = relationship(back_populates="user")
    password_reset_tokens: Mapped[list[PasswordResetTokenRecord]] = relationship(
        back_populates="user"
    )
    email_verification_tokens: Mapped[list[EmailVerificationTokenRecord]] = relationship(
        back_populates="user"
    )
    sent_invitations: Mapped[list[OrganizationInvitationRecord]] = relationship(
        back_populates="invited_by", foreign_keys="OrganizationInvitationRecord.invited_by_user_id"
    )
    dataset_reviews: Mapped[list[DatasetReviewRecord]] = relationship(
        back_populates="reviewer"
    )


class MembershipRecord(TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id"),
        CheckConstraint(
            "role IN ('OWNER', 'ADMIN', 'ENGINEER', 'REVIEWER', 'VIEWER')",
            name="valid_role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(30), nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="memberships")
    user: Mapped[UserRecord] = relationship(back_populates="memberships")


class OrganizationInvitationRecord(TimestampMixin, Base):
    __tablename__ = "organization_invitations"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="invitation_email_normalized"),
        CheckConstraint(
            "role IN ('OWNER', 'ADMIN', 'ENGINEER', 'REVIEWER', 'VIEWER')",
            name="invitation_valid_role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    invited_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    organization: Mapped[Organization] = relationship(back_populates="invitations")
    invited_by: Mapped[UserRecord] = relationship(
        back_populates="sent_invitations", foreign_keys=[invited_by_user_id]
    )


class AuthSessionRecord(TimestampMixin, Base):
    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[UserRecord] = relationship(back_populates="sessions")


class PasswordResetTokenRecord(TimestampMixin, Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[UserRecord] = relationship(back_populates="password_reset_tokens")


class EmailVerificationTokenRecord(TimestampMixin, Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[UserRecord] = relationship(back_populates="email_verification_tokens")


class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("organization_id", "slug"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="projects")
    catalogs: Mapped[list[CatalogRecord]] = relationship(back_populates="project")
    datasets: Mapped[list[DatasetRecord]] = relationship(back_populates="project")
    search_systems: Mapped[list[SearchSystemRecord]] = relationship(back_populates="project")
    evaluation_runs: Mapped[list[EvaluationRunRecord]] = relationship(back_populates="project")


class CatalogRecord(TimestampMixin, Base):
    __tablename__ = "catalogs"
    __table_args__ = (
        UniqueConstraint("project_id", "name"),
        UniqueConstraint(
            "project_id", "external_id", name="uq_catalogs_project_external_id"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(200), index=True)

    project: Mapped[Project] = relationship(back_populates="catalogs")
    versions: Mapped[list[CatalogVersionRecord]] = relationship(back_populates="catalog")


class CatalogVersionRecord(TimestampMixin, Base):
    __tablename__ = "catalog_versions"
    __table_args__ = (UniqueConstraint("catalog_id", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    catalog_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("catalogs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT")
    content_hash: Mapped[str | None] = mapped_column(String(64))
    artifact_hash: Mapped[str | None] = mapped_column(String(64))
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    catalog: Mapped[CatalogRecord] = relationship(back_populates="versions")
    products: Mapped[list[ProductRecord]] = relationship(back_populates="catalog_version")


class ProductRecord(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("catalog_version_id", "product_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    catalog_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("catalog_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    catalog_version: Mapped[CatalogVersionRecord] = relationship(back_populates="products")


class DatasetRecord(TimestampMixin, Base):
    __tablename__ = "datasets"
    __table_args__ = (
        UniqueConstraint("project_id", "name"),
        UniqueConstraint(
            "project_id", "external_id", name="uq_datasets_project_external_id"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(200), index=True)

    project: Mapped[Project] = relationship(back_populates="datasets")
    versions: Mapped[list[DatasetVersionRecord]] = relationship(back_populates="dataset")


class DatasetVersionRecord(TimestampMixin, Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    catalog_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("catalog_versions.id", ondelete="RESTRICT"), index=True
    )
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT")
    content_hash: Mapped[str | None] = mapped_column(String(64))
    artifact_hash: Mapped[str | None] = mapped_column(String(64))
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    dataset: Mapped[DatasetRecord] = relationship(back_populates="versions")
    cases: Mapped[list[EvaluationCaseRecord]] = relationship(back_populates="dataset_version")
    reviews: Mapped[list[DatasetReviewRecord]] = relationship(
        back_populates="dataset_version"
    )


class EvaluationCaseRecord(TimestampMixin, Base):
    __tablename__ = "evaluation_cases"
    __table_args__ = (UniqueConstraint("dataset_version_id", "case_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    case_id: Mapped[str] = mapped_column(String(200), nullable=False)
    query: Mapped[str] = mapped_column(String(2000), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    dataset_version: Mapped[DatasetVersionRecord] = relationship(back_populates="cases")


class DatasetReviewRecord(TimestampMixin, Base):
    __tablename__ = "dataset_reviews"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('APPROVED', 'REJECTED')", name="valid_decision"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewer_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    note: Mapped[str | None] = mapped_column(String(2000))

    dataset_version: Mapped[DatasetVersionRecord] = relationship(back_populates="reviews")
    reviewer: Mapped[UserRecord] = relationship(back_populates="dataset_reviews")


class SearchSystemRecord(TimestampMixin, Base):
    __tablename__ = "search_systems"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)

    project: Mapped[Project] = relationship(back_populates="search_systems")
    versions: Mapped[list[SearchSystemVersionRecord]] = relationship(
        back_populates="search_system"
    )


class SearchSystemVersionRecord(TimestampMixin, Base):
    __tablename__ = "search_system_versions"
    __table_args__ = (UniqueConstraint("search_system_id", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    search_system_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("search_systems.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(200), nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    search_system: Mapped[SearchSystemRecord] = relationship(back_populates="versions")
    evaluation_runs: Mapped[list[EvaluationRunRecord]] = relationship(
        back_populates="search_system_version"
    )


class EvaluationRunRecord(TimestampMixin, Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (UniqueConstraint("organization_id", "external_run_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    search_system_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("search_system_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    external_run_id: Mapped[str] = mapped_column(String(200), nullable=False)
    result_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_uri: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    dataset_id: Mapped[str] = mapped_column(String(200), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(200), nullable=False)
    dataset_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    catalog_id: Mapped[str] = mapped_column(String(200), nullable=False)
    catalog_version: Mapped[str] = mapped_column(String(200), nullable=False)
    adapter_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    trace_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_definition_version: Mapped[str] = mapped_column(String(200), nullable=False)
    top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    case_count: Mapped[int] = mapped_column(Integer, nullable=False)
    passed_case_count: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_case_count: Mapped[int] = mapped_column(Integer, nullable=False)
    aggregate_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    failure_counts: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    project: Mapped[Project] = relationship(back_populates="evaluation_runs")
    search_system_version: Mapped[SearchSystemVersionRecord] = relationship(
        back_populates="evaluation_runs"
    )
    case_results: Mapped[list[CaseResultRecord]] = relationship(
        back_populates="evaluation_run"
    )


class EvaluationJobRecord(TimestampMixin, Base):
    __tablename__ = "evaluation_jobs"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key"),
        CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'COMPLETED', "
            "'COMPLETED_WITH_ERRORS', 'FAILED', 'CANCELLED')",
            name="valid_status",
        ),
        CheckConstraint("completed_case_count >= 0", name="completed_non_negative"),
        CheckConstraint("total_case_count >= 0", name="total_non_negative"),
        CheckConstraint(
            "completed_case_count <= total_case_count", name="completed_within_total"
        ),
        CheckConstraint("attempt_count >= 0", name="attempt_non_negative"),
        CheckConstraint("max_attempts >= 1", name="max_attempts_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    search_system_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("search_system_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    evaluation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="SET NULL"), index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="QUEUED")
    completed_case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_case_count: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    top_k: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    seed: Mapped[int] = mapped_column(Integer, nullable=False, default=42)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_detail: Mapped[str | None] = mapped_column(String(1000))


class WorkerHeartbeatRecord(TimestampMixin, Base):
    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    current_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evaluation_jobs.id", ondelete="SET NULL"), index=True
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class CaseResultRecord(TimestampMixin, Base):
    __tablename__ = "case_results"
    __table_args__ = (UniqueConstraint("evaluation_run_id", "case_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    case_id: Mapped[str] = mapped_column(String(200), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    expected_product_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    actual_product_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    false_positives: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    false_negatives: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(200))
    trace_url: Mapped[str | None] = mapped_column(Text)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)

    evaluation_run: Mapped[EvaluationRunRecord] = relationship(back_populates="case_results")
    metrics: Mapped[list[MetricResultRecord]] = relationship(back_populates="case_result")
    failures: Mapped[list[FailureRecord]] = relationship(back_populates="case_result")


class MetricResultRecord(TimestampMixin, Base):
    __tablename__ = "metric_results"
    __table_args__ = (UniqueConstraint("case_result_id", "metric_name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    case_result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case_results.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_name: Mapped[str] = mapped_column(String(200), nullable=False)
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[float | None] = mapped_column(Float)
    passed: Mapped[bool | None] = mapped_column(Boolean)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)

    case_result: Mapped[CaseResultRecord] = relationship(back_populates="metrics")


class FailureRecord(TimestampMixin, Base):
    __tablename__ = "failures"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    case_result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case_results.id", ondelete="CASCADE"), nullable=False, index=True
    )
    failure_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    component: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    case_result: Mapped[CaseResultRecord] = relationship(back_populates="failures")

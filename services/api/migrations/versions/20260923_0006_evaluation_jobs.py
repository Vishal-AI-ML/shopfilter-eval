from __future__ import annotations

"""Add durable evaluation jobs and worker heartbeats.

Revision ID: 20260923_0006
Revises: 20260923_0005
"""
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "20260923_0006"
down_revision: str | None = "20260923_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[Any]]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "evaluation_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("search_system_version_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_run_id", sa.Uuid()),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("completed_case_count", sa.Integer(), nullable=False),
        sa.Column("total_case_count", sa.Integer(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(100)),
        sa.Column("error_detail", sa.String(1000)),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'COMPLETED', "
            "'COMPLETED_WITH_ERRORS', 'FAILED', 'CANCELLED')",
            name=op.f("ck_evaluation_jobs_valid_status"),
        ),
        sa.CheckConstraint(
            "completed_case_count >= 0",
            name=op.f("ck_evaluation_jobs_completed_non_negative"),
        ),
        sa.CheckConstraint(
            "total_case_count >= 0",
            name=op.f("ck_evaluation_jobs_total_non_negative"),
        ),
        sa.CheckConstraint(
            "completed_case_count <= total_case_count",
            name=op.f("ck_evaluation_jobs_completed_within_total"),
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name=op.f("ck_evaluation_jobs_attempt_non_negative"),
        ),
        sa.CheckConstraint(
            "max_attempts >= 1",
            name=op.f("ck_evaluation_jobs_max_attempts_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"], ["dataset_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["search_system_version_id"],
            ["search_system_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_run_id"], ["evaluation_runs.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evaluation_jobs")),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name=op.f("uq_evaluation_jobs_organization_id"),
        ),
        sa.UniqueConstraint(
            "evaluation_run_id", name=op.f("uq_evaluation_jobs_evaluation_run_id")
        ),
    )
    for column in (
        "organization_id",
        "project_id",
        "dataset_version_id",
        "search_system_version_id",
        "requested_by_user_id",
        "evaluation_run_id",
        "status",
    ):
        op.create_index(
            op.f(f"ix_evaluation_jobs_{column}"), "evaluation_jobs", [column]
        )

    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_id", sa.String(200), nullable=False),
        sa.Column("current_job_id", sa.Uuid()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["current_job_id"], ["evaluation_jobs.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("worker_id", name=op.f("pk_worker_heartbeats")),
    )
    op.create_index(
        op.f("ix_worker_heartbeats_current_job_id"),
        "worker_heartbeats",
        ["current_job_id"],
    )


def downgrade() -> None:
    op.drop_table("worker_heartbeats")
    op.drop_table("evaluation_jobs")

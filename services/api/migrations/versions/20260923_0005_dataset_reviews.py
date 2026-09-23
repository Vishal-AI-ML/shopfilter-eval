from __future__ import annotations

"""Add append-only human dataset review decisions.

Revision ID: 20260923_0005
Revises: 20260923_0004
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260923_0005"
down_revision: str | None = "20260923_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dataset_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("note", sa.String(2000)),
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
        sa.CheckConstraint(
            "decision IN ('APPROVED', 'REJECTED')",
            name=op.f("ck_dataset_reviews_valid_decision"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
            name=op.f("fk_dataset_reviews_organization_id_organizations"),
        ),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"],
            ["dataset_versions.id"],
            ondelete="CASCADE",
            name=op.f("fk_dataset_reviews_dataset_version_id_dataset_versions"),
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
            name=op.f("fk_dataset_reviews_reviewer_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataset_reviews")),
    )
    op.create_index(
        op.f("ix_dataset_reviews_organization_id"),
        "dataset_reviews",
        ["organization_id"],
    )
    op.create_index(
        op.f("ix_dataset_reviews_dataset_version_id"),
        "dataset_reviews",
        ["dataset_version_id"],
    )
    op.create_index(
        op.f("ix_dataset_reviews_reviewer_user_id"),
        "dataset_reviews",
        ["reviewer_user_id"],
    )


def downgrade() -> None:
    op.drop_table("dataset_reviews")

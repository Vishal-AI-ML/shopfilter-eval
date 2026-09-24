from __future__ import annotations

"""Add secure organization invitations.

Revision ID: 20260924_0010
Revises: 20260924_0009
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260924_0010"
down_revision: str | None = "20260924_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization_invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("invited_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_organization_invitations_invitation_email_normalized")),
        sa.CheckConstraint("role IN ('OWNER', 'ADMIN', 'ENGINEER', 'REVIEWER', 'VIEWER')", name=op.f("ck_organization_invitations_invitation_valid_role")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE", name=op.f("fk_organization_invitations_organization_id_organizations")),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"], ondelete="RESTRICT", name=op.f("fk_organization_invitations_invited_by_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organization_invitations")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_organization_invitations_token_hash")),
    )
    for column in ("organization_id", "email", "invited_by_user_id", "token_hash", "expires_at"):
        op.create_index(op.f(f"ix_organization_invitations_{column}"), "organization_invitations", [column], unique=column == "token_hash")


def downgrade() -> None:
    op.drop_table("organization_invitations")

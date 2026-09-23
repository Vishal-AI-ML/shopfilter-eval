from __future__ import annotations

"""Add immutable catalog and dataset artifact provenance.

Revision ID: 20260923_0003
Revises: 20260923_0002
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260923_0003"
down_revision: str | None = "20260923_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("catalogs") as batch:
        batch.add_column(sa.Column("external_id", sa.String(200)))
        batch.create_index("ix_catalogs_external_id", ["external_id"])
        batch.create_unique_constraint(
            "uq_catalogs_project_external_id", ["project_id", "external_id"]
        )
    with op.batch_alter_table("datasets") as batch:
        batch.add_column(sa.Column("external_id", sa.String(200)))
        batch.create_index("ix_datasets_external_id", ["external_id"])
        batch.create_unique_constraint(
            "uq_datasets_project_external_id", ["project_id", "external_id"]
        )
    for table in ("catalog_versions", "dataset_versions"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("artifact_hash", sa.String(64)))
            batch.add_column(
                sa.Column("item_count", sa.Integer(), nullable=False, server_default="0")
            )
            batch.add_column(
                sa.Column("provenance", sa.JSON(), nullable=False, server_default="{}")
            )


def downgrade() -> None:
    for table in ("dataset_versions", "catalog_versions"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("provenance")
            batch.drop_column("item_count")
            batch.drop_column("artifact_hash")
    with op.batch_alter_table("datasets") as batch:
        batch.drop_constraint("uq_datasets_project_external_id", type_="unique")
        batch.drop_index("ix_datasets_external_id")
        batch.drop_column("external_id")
    with op.batch_alter_table("catalogs") as batch:
        batch.drop_constraint("uq_catalogs_project_external_id", type_="unique")
        batch.drop_index("ix_catalogs_external_id")
        batch.drop_column("external_id")

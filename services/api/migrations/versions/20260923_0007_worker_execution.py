from __future__ import annotations

"""Allow idempotent jobs to reference a shared immutable run.

Revision ID: 20260923_0007
Revises: 20260923_0006
"""
from collections.abc import Sequence

from alembic import op

revision: str = "20260923_0007"
down_revision: str | None = "20260923_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("evaluation_jobs") as batch:
        batch.drop_constraint(
            "uq_evaluation_jobs_evaluation_run_id", type_="unique"
        )


def downgrade() -> None:
    with op.batch_alter_table("evaluation_jobs") as batch:
        batch.create_unique_constraint(
            "uq_evaluation_jobs_evaluation_run_id", ["evaluation_run_id"]
        )

from __future__ import annotations

"""Generalize persisted search systems into backward-compatible AI systems.

Revision ID: 20260925_0011
Revises: 20260924_0010
"""

import hashlib
import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "20260925_0011"
down_revision: str | None = "20260924_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        loaded = json.loads(value)
        if isinstance(loaded, dict):
            return loaded
    raise ValueError("AI system version configuration must be a JSON object")


def _content_hash(version: str, configuration: dict[str, Any]) -> str:
    canonical = json.dumps(
        {
            "capabilities": {},
            "configuration": configuration,
            "version": version,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def upgrade() -> None:
    op.add_column(
        "search_systems",
        sa.Column(
            "system_type",
            sa.String(40),
            nullable=False,
            server_default="LEXICAL_SEARCH",
        ),
    )
    op.add_column(
        "search_systems", sa.Column("description", sa.Text(), nullable=True)
    )
    op.add_column(
        "search_systems",
        sa.Column("status", sa.String(30), nullable=False, server_default="ACTIVE"),
    )
    op.add_column(
        "search_system_versions",
        sa.Column("capabilities", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "search_system_versions",
        sa.Column(
            "status", sa.String(30), nullable=False, server_default="PUBLISHED"
        ),
    )
    op.add_column(
        "search_system_versions",
        sa.Column("content_hash", sa.String(64), nullable=True),
    )

    connection = op.get_bind()
    versions = sa.table(
        "search_system_versions",
        sa.column("id", sa.Uuid()),
        sa.column("version", sa.String()),
        sa.column("configuration", sa.JSON()),
        sa.column("content_hash", sa.String()),
    )
    for row in connection.execute(
        sa.select(versions.c.id, versions.c.version, versions.c.configuration)
    ).mappings():
        connection.execute(
            versions.update()
            .where(versions.c.id == row["id"])
            .values(
                content_hash=_content_hash(
                    row["version"], _json_object(row["configuration"])
                )
            )
        )

    with op.batch_alter_table("search_system_versions") as batch_op:
        batch_op.alter_column(
            "content_hash", existing_type=sa.String(64), nullable=False
        )
        batch_op.create_check_constraint(
            "ck_search_system_versions_valid_ai_system_version_status",
            "status IN ('PUBLISHED', 'ARCHIVED')",
        )

    with op.batch_alter_table("search_systems") as batch_op:
        batch_op.create_check_constraint(
            "ck_search_systems_valid_system_type",
            "system_type IN ('LEXICAL_SEARCH', 'SEMANTIC_SEARCH', 'HYBRID_SEARCH', "
            "'RAG_ASSISTANT', 'EXTERNAL_SEARCH_API', 'EXTERNAL_ASSISTANT_API')",
        )
        batch_op.create_check_constraint(
            "ck_search_systems_valid_ai_system_status",
            "status IN ('ACTIVE', 'ARCHIVED')",
        )


def downgrade() -> None:
    with op.batch_alter_table("search_system_versions") as batch_op:
        batch_op.drop_constraint(
            "ck_search_system_versions_valid_ai_system_version_status",
            type_="check",
        )
        batch_op.drop_column("content_hash")
        batch_op.drop_column("status")
        batch_op.drop_column("capabilities")

    with op.batch_alter_table("search_systems") as batch_op:
        batch_op.drop_constraint(
            "ck_search_systems_valid_ai_system_status", type_="check"
        )
        batch_op.drop_constraint(
            "ck_search_systems_valid_system_type", type_="check"
        )
        batch_op.drop_column("status")
        batch_op.drop_column("description")
        batch_op.drop_column("system_type")


from __future__ import annotations

"""Initial tenant-aware persistence schema.

Revision ID: 20260923_0001
Revises:
"""
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "20260923_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[Any]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
        sa.UniqueConstraint("slug", name=op.f("uq_organizations_slug")),
    )
    op.create_index(op.f("ix_organizations_slug"), "organizations", ["slug"], unique=True)
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE", name=op.f("fk_projects_organization_id_organizations")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
        sa.UniqueConstraint("organization_id", "slug", name=op.f("uq_projects_organization_id")),
    )
    op.create_index(op.f("ix_projects_organization_id"), "projects", ["organization_id"])
    op.create_table(
        "catalogs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE", name=op.f("fk_catalogs_organization_id_organizations")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE", name=op.f("fk_catalogs_project_id_projects")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalogs")),
        sa.UniqueConstraint("project_id", "name", name=op.f("uq_catalogs_project_id")),
    )
    op.create_index(op.f("ix_catalogs_organization_id"), "catalogs", ["organization_id"])
    op.create_index(op.f("ix_catalogs_project_id"), "catalogs", ["project_id"])
    op.create_table(
        "catalog_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("catalog_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE", name=op.f("fk_catalog_versions_organization_id_organizations")),
        sa.ForeignKeyConstraint(["catalog_id"], ["catalogs.id"], ondelete="CASCADE", name=op.f("fk_catalog_versions_catalog_id_catalogs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalog_versions")),
        sa.UniqueConstraint("catalog_id", "version", name=op.f("uq_catalog_versions_catalog_id")),
    )
    op.create_index(op.f("ix_catalog_versions_organization_id"), "catalog_versions", ["organization_id"])
    op.create_index(op.f("ix_catalog_versions_catalog_id"), "catalog_versions", ["catalog_id"])
    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("catalog_version_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=1000), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE", name=op.f("fk_products_organization_id_organizations")),
        sa.ForeignKeyConstraint(["catalog_version_id"], ["catalog_versions.id"], ondelete="CASCADE", name=op.f("fk_products_catalog_version_id_catalog_versions")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
        sa.UniqueConstraint("catalog_version_id", "product_id", name=op.f("uq_products_catalog_version_id")),
    )
    op.create_index(op.f("ix_products_organization_id"), "products", ["organization_id"])
    op.create_index(op.f("ix_products_catalog_version_id"), "products", ["catalog_version_id"])
    op.create_table(
        "datasets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE", name=op.f("fk_datasets_organization_id_organizations")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE", name=op.f("fk_datasets_project_id_projects")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_datasets")),
        sa.UniqueConstraint("project_id", "name", name=op.f("uq_datasets_project_id")),
    )
    op.create_index(op.f("ix_datasets_organization_id"), "datasets", ["organization_id"])
    op.create_index(op.f("ix_datasets_project_id"), "datasets", ["project_id"])
    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("catalog_version_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE", name=op.f("fk_dataset_versions_organization_id_organizations")),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE", name=op.f("fk_dataset_versions_dataset_id_datasets")),
        sa.ForeignKeyConstraint(["catalog_version_id"], ["catalog_versions.id"], ondelete="RESTRICT", name=op.f("fk_dataset_versions_catalog_version_id_catalog_versions")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataset_versions")),
        sa.UniqueConstraint("dataset_id", "version", name=op.f("uq_dataset_versions_dataset_id")),
    )
    op.create_index(op.f("ix_dataset_versions_organization_id"), "dataset_versions", ["organization_id"])
    op.create_index(op.f("ix_dataset_versions_dataset_id"), "dataset_versions", ["dataset_id"])
    op.create_index(op.f("ix_dataset_versions_catalog_version_id"), "dataset_versions", ["catalog_version_id"])
    op.create_table(
        "evaluation_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.String(length=200), nullable=False),
        sa.Column("query", sa.String(length=2000), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE", name=op.f("fk_evaluation_cases_organization_id_organizations")),
        sa.ForeignKeyConstraint(["dataset_version_id"], ["dataset_versions.id"], ondelete="CASCADE", name=op.f("fk_evaluation_cases_dataset_version_id_dataset_versions")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evaluation_cases")),
        sa.UniqueConstraint("dataset_version_id", "case_id", name=op.f("uq_evaluation_cases_dataset_version_id")),
    )
    op.create_index(op.f("ix_evaluation_cases_organization_id"), "evaluation_cases", ["organization_id"])
    op.create_index(op.f("ix_evaluation_cases_dataset_version_id"), "evaluation_cases", ["dataset_version_id"])


def downgrade() -> None:
    op.drop_table("evaluation_cases")
    op.drop_table("dataset_versions")
    op.drop_table("datasets")
    op.drop_table("products")
    op.drop_table("catalog_versions")
    op.drop_table("catalogs")
    op.drop_table("projects")
    op.drop_table("organizations")

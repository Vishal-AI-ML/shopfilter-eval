
from __future__ import annotations

"""Persist search systems and evaluation evidence.

Revision ID: 20260923_0002
Revises: 20260923_0001
"""
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "20260923_0002"
down_revision: str | None = "20260923_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[Any]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def _tenant_id() -> sa.Column[Any]:
    return sa.Column("organization_id", sa.Uuid(), nullable=False)


def upgrade() -> None:
    op.create_table(
        "search_systems",
        sa.Column("id", sa.Uuid(), nullable=False), _tenant_id(),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False), *_timestamps(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE", name=op.f("fk_search_systems_organization_id_organizations")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE", name=op.f("fk_search_systems_project_id_projects")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_systems")),
        sa.UniqueConstraint("project_id", "name", name=op.f("uq_search_systems_project_id")),
    )
    op.create_index(op.f("ix_search_systems_organization_id"), "search_systems", ["organization_id"])
    op.create_index(op.f("ix_search_systems_project_id"), "search_systems", ["project_id"])
    op.create_table(
        "search_system_versions",
        sa.Column("id", sa.Uuid(), nullable=False), _tenant_id(),
        sa.Column("search_system_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(200), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False), *_timestamps(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE", name=op.f("fk_search_system_versions_organization_id_organizations")),
        sa.ForeignKeyConstraint(["search_system_id"], ["search_systems.id"], ondelete="CASCADE", name=op.f("fk_search_system_versions_search_system_id_search_systems")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_system_versions")),
        sa.UniqueConstraint("search_system_id", "version", name=op.f("uq_search_system_versions_search_system_id")),
    )
    op.create_index(op.f("ix_search_system_versions_organization_id"), "search_system_versions", ["organization_id"])
    op.create_index(op.f("ix_search_system_versions_search_system_id"), "search_system_versions", ["search_system_id"])
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.Uuid(), nullable=False), _tenant_id(),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("search_system_version_id", sa.Uuid(), nullable=False),
        sa.Column("external_run_id", sa.String(200), nullable=False),
        sa.Column("result_fingerprint", sa.String(64), nullable=False),
        sa.Column("artifact_hash", sa.String(64), nullable=False),
        sa.Column("artifact_uri", sa.Text()), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("dataset_id", sa.String(200), nullable=False), sa.Column("dataset_version", sa.String(200), nullable=False),
        sa.Column("dataset_hash", sa.String(64), nullable=False), sa.Column("catalog_id", sa.String(200), nullable=False),
        sa.Column("catalog_version", sa.String(200), nullable=False), sa.Column("adapter_provider", sa.String(100), nullable=False),
        sa.Column("trace_provider", sa.String(100), nullable=False), sa.Column("metric_definition_version", sa.String(200), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False), sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False), sa.Column("passed_case_count", sa.Integer(), nullable=False),
        sa.Column("failed_case_count", sa.Integer(), nullable=False), sa.Column("aggregate_metrics", sa.JSON(), nullable=False),
        sa.Column("failure_counts", sa.JSON(), nullable=False), *_timestamps(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE", name=op.f("fk_evaluation_runs_organization_id_organizations")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE", name=op.f("fk_evaluation_runs_project_id_projects")),
        sa.ForeignKeyConstraint(["search_system_version_id"], ["search_system_versions.id"], ondelete="RESTRICT", name=op.f("fk_evaluation_runs_search_system_version_id_search_system_versions")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evaluation_runs")),
        sa.UniqueConstraint("organization_id", "external_run_id", name=op.f("uq_evaluation_runs_organization_id")),
    )
    for column in ("organization_id", "project_id", "search_system_version_id"):
        op.create_index(op.f(f"ix_evaluation_runs_{column}"), "evaluation_runs", [column])
    op.create_table(
        "case_results",
        sa.Column("id", sa.Uuid(), nullable=False), _tenant_id(),
        sa.Column("evaluation_run_id", sa.Uuid(), nullable=False), sa.Column("case_id", sa.String(200), nullable=False),
        sa.Column("query", sa.Text(), nullable=False), sa.Column("expected_product_ids", sa.JSON(), nullable=False),
        sa.Column("actual_product_ids", sa.JSON(), nullable=False), sa.Column("false_positives", sa.JSON(), nullable=False),
        sa.Column("false_negatives", sa.JSON(), nullable=False), sa.Column("trace_id", sa.String(200)),
        sa.Column("trace_url", sa.Text()), sa.Column("passed", sa.Boolean(), nullable=False), *_timestamps(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE", name=op.f("fk_case_results_organization_id_organizations")),
        sa.ForeignKeyConstraint(["evaluation_run_id"], ["evaluation_runs.id"], ondelete="CASCADE", name=op.f("fk_case_results_evaluation_run_id_evaluation_runs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_case_results")),
        sa.UniqueConstraint("evaluation_run_id", "case_id", name=op.f("uq_case_results_evaluation_run_id")),
    )
    op.create_index(op.f("ix_case_results_organization_id"), "case_results", ["organization_id"])
    op.create_index(op.f("ix_case_results_evaluation_run_id"), "case_results", ["evaluation_run_id"])
    op.create_table(
        "metric_results",
        sa.Column("id", sa.Uuid(), nullable=False), _tenant_id(), sa.Column("case_result_id", sa.Uuid(), nullable=False),
        sa.Column("metric_name", sa.String(200), nullable=False), sa.Column("metric_type", sa.String(50), nullable=False),
        sa.Column("value", sa.Float()), sa.Column("passed", sa.Boolean()), sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text()), *_timestamps(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE", name=op.f("fk_metric_results_organization_id_organizations")),
        sa.ForeignKeyConstraint(["case_result_id"], ["case_results.id"], ondelete="CASCADE", name=op.f("fk_metric_results_case_result_id_case_results")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_metric_results")),
        sa.UniqueConstraint("case_result_id", "metric_name", name=op.f("uq_metric_results_case_result_id")),
    )
    op.create_index(op.f("ix_metric_results_organization_id"), "metric_results", ["organization_id"])
    op.create_index(op.f("ix_metric_results_case_result_id"), "metric_results", ["case_result_id"])
    op.create_table(
        "failures",
        sa.Column("id", sa.Uuid(), nullable=False), _tenant_id(), sa.Column("case_result_id", sa.Uuid(), nullable=False),
        sa.Column("failure_type", sa.String(100), nullable=False), sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("component", sa.String(100), nullable=False), sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False), sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text()), *_timestamps(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE", name=op.f("fk_failures_organization_id_organizations")),
        sa.ForeignKeyConstraint(["case_result_id"], ["case_results.id"], ondelete="CASCADE", name=op.f("fk_failures_case_result_id_case_results")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_failures")),
    )
    op.create_index(op.f("ix_failures_organization_id"), "failures", ["organization_id"])
    op.create_index(op.f("ix_failures_case_result_id"), "failures", ["case_result_id"])
    op.create_index(op.f("ix_failures_failure_type"), "failures", ["failure_type"])


def downgrade() -> None:
    op.drop_table("failures")
    op.drop_table("metric_results")
    op.drop_table("case_results")
    op.drop_table("evaluation_runs")
    op.drop_table("search_system_versions")
    op.drop_table("search_systems")

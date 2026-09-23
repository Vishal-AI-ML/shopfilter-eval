from sqlalchemy import inspect

from services.api.shopfilter_api import models  # noqa: F401
from services.api.shopfilter_api.database import Base


def test_initial_metadata_contains_expected_tables() -> None:
    assert set(Base.metadata.tables) == {
        "organizations",
        "users",
        "memberships",
        "auth_sessions",
        "projects",
        "catalogs",
        "catalog_versions",
        "products",
        "datasets",
        "dataset_versions",
        "dataset_reviews",
        "evaluation_cases",
        "search_systems",
        "search_system_versions",
        "evaluation_runs",
        "case_results",
        "metric_results",
        "failures",
    }


def test_every_tenant_owned_table_has_organization_id() -> None:
    globally_scoped = {"organizations", "users", "auth_sessions"}
    for table_name in set(Base.metadata.tables) - globally_scoped:
        columns = {
            column.name
            for column in inspect(Base.metadata.tables[table_name]).columns
        }
        assert "organization_id" in columns, table_name

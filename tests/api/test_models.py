
from sqlalchemy import inspect

from services.api.shopfilter_api import models  # noqa: F401
from services.api.shopfilter_api.database import Base


def test_initial_metadata_contains_expected_tables() -> None:
    assert set(Base.metadata.tables) == {
        "organizations",
        "projects",
        "catalogs",
        "catalog_versions",
        "products",
        "datasets",
        "dataset_versions",
        "evaluation_cases",
    }


def test_every_tenant_owned_table_has_organization_id() -> None:
    for table_name in set(Base.metadata.tables) - {"organizations"}:
        columns = {column.name for column in inspect(Base.metadata.tables[table_name]).columns}
        assert "organization_id" in columns, table_name

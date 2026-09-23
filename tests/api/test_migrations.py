from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from services.api.shopfilter_api.config import get_settings
from services.api.shopfilter_api.models import Organization, Project
from services.api.shopfilter_api.seed import seed_demo

EXPECTED_TABLES = {
    "alembic_version",
    "organizations",
    "projects",
    "catalogs",
    "catalog_versions",
    "products",
    "datasets",
    "dataset_versions",
    "evaluation_cases",
    "search_systems",
    "search_system_versions",
    "evaluation_runs",
    "case_results",
    "metric_results",
    "failures",
}


def _migration_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_migration_upgrades_empty_database(tmp_path: Path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'migration.sqlite3'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    command.upgrade(_migration_config(database_url), "head")
    engine = create_engine(database_url)
    try:
        assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES
    finally:
        engine.dispose()
        get_settings.cache_clear()


def test_demo_seed_is_idempotent_after_migration(tmp_path: Path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'seed.sqlite3'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    command.upgrade(_migration_config(database_url), "head")
    seed_demo()
    seed_demo()
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            assert len(list(session.scalars(select(Organization)))) == 1
            assert len(list(session.scalars(select(Project)))) == 1
    finally:
        engine.dispose()
        get_settings.cache_clear()

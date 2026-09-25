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
    "users",
    "memberships",
    "auth_sessions",
    "password_reset_tokens",
    "email_verification_tokens",
    "organization_invitations",
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
    "evaluation_jobs",
    "worker_heartbeats",
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


def test_ai_system_migration_backfills_existing_search_data(
    tmp_path: Path, monkeypatch
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'ai-system-migration.sqlite3'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = _migration_config(database_url)
    command.upgrade(config, "20260924_0010")
    engine = create_engine(database_url)
    organization_id = "00000000000000000000000000000001"
    project_id = "00000000000000000000000000000002"
    system_id = "00000000000000000000000000000003"
    version_id = "00000000000000000000000000000004"
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO organizations (id, name, slug) VALUES (?, ?, ?)",
            (organization_id, "Legacy Organization", "legacy-organization"),
        )
        connection.exec_driver_sql(
            "INSERT INTO projects (id, organization_id, name, slug) VALUES (?, ?, ?, ?)",
            (project_id, organization_id, "Legacy Project", "legacy-project"),
        )
        connection.exec_driver_sql(
            "INSERT INTO search_systems "
            "(id, organization_id, project_id, name, provider) VALUES (?, ?, ?, ?, ?)",
            (system_id, organization_id, project_id, "Legacy Search", "demo"),
        )
        connection.exec_driver_sql(
            "INSERT INTO search_system_versions "
            "(id, organization_id, search_system_id, version, configuration) "
            "VALUES (?, ?, ?, ?, ?)",
            (version_id, organization_id, system_id, "v1", '{"top_k": 10}'),
        )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        system = connection.exec_driver_sql(
            "SELECT system_type, status, description FROM search_systems WHERE id = ?",
            (system_id,),
        ).mappings().one()
        version = connection.exec_driver_sql(
            "SELECT capabilities, status, content_hash "
            "FROM search_system_versions WHERE id = ?",
            (version_id,),
        ).mappings().one()
    assert system == {
        "system_type": "LEXICAL_SEARCH",
        "status": "ACTIVE",
        "description": None,
    }
    assert version["capabilities"] == "{}"
    assert version["status"] == "PUBLISHED"
    assert len(version["content_hash"]) == 64
    engine.dispose()

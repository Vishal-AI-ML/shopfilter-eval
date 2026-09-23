from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from packages.evaluation_engine.datasets import GoldenDataset, compute_dataset_hash
from services.api.shopfilter_api.database import Base
from services.api.shopfilter_api.models import (
    CatalogVersionRecord,
    EvaluationCaseRecord,
    Organization,
    ProductRecord,
    Project,
)
from services.api.shopfilter_api.version_persistence import (
    VersionImportError,
    import_catalog_artifact,
    import_dataset_artifact,
)


@pytest.fixture
def db_session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'versions.sqlite3'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def seeded_scope(db_session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    organization = Organization(name="Primary", slug="primary")
    db_session.add(organization)
    db_session.flush()
    project = Project(
        organization_id=organization.id, name="Search", slug="search"
    )
    db_session.add(project)
    db_session.commit()
    return organization.id, project.id


@pytest.fixture
def second_scope(db_session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    organization = Organization(name="Secondary", slug="secondary")
    db_session.add(organization)
    db_session.flush()
    project = Project(
        organization_id=organization.id, name="Search", slug="search"
    )
    db_session.add(project)
    db_session.commit()
    return organization.id, project.id


def _write(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _catalog(path: Path, *, title: str = "Running Shoe") -> Path:
    return _write(
        path,
        {
            "catalog_id": "catalog-one",
            "version": "v1",
            "products": [
                {
                    "product_id": "P-1",
                    "title": title,
                    "category": "shoes",
                    "price": "99.00",
                    "currency": "USD",
                }
            ],
        },
    )


def _dataset(path: Path, *, product_id: str = "P-1") -> Path:
    base = {
        "dataset_id": "dataset-one",
        "version": "v1",
        "catalog_id": "catalog-one",
        "catalog_version": "v1",
        "status": "APPROVED",
        "cases": [
            {
                "case_id": "C-1",
                "case_type": "retrieval",
                "query": "running shoe",
                "expected_query_text": "running shoe",
                "expected_constraints": {},
                "expected_products": [
                    {"product_id": product_id, "relevance": "E", "expected_rank": 1}
                ],
                "difficulty": "normal",
                "source": "test",
                "review_status": "APPROVED",
            }
        ],
    }
    placeholder = GoldenDataset.model_validate({**base, "content_hash": "0" * 64})
    payload = {
        **base,
        "content_hash": compute_dataset_hash(placeholder),
    }
    return _write(path, payload)


def test_catalog_and_dataset_import_are_idempotent(
    db_session: Session,
    seeded_scope: tuple[uuid.UUID, uuid.UUID],
    tmp_path: Path,
) -> None:
    organization_id, project_id = seeded_scope
    catalog_path = _catalog(tmp_path / "catalog.json")
    dataset_path = _dataset(tmp_path / "dataset.json")

    catalog = import_catalog_artifact(
        db_session,
        organization_id=organization_id,
        project_id=project_id,
        artifact_path=catalog_path,
    )
    dataset = import_dataset_artifact(
        db_session,
        organization_id=organization_id,
        project_id=project_id,
        artifact_path=dataset_path,
    )
    catalog_again = import_catalog_artifact(
        db_session,
        organization_id=organization_id,
        project_id=project_id,
        artifact_path=catalog_path,
    )
    dataset_again = import_dataset_artifact(
        db_session,
        organization_id=organization_id,
        project_id=project_id,
        artifact_path=dataset_path,
    )

    assert catalog.created is True
    assert dataset.created is True
    assert catalog_again.created is False
    assert dataset_again.created is False
    assert db_session.scalar(select(func.count(ProductRecord.id))) == 1
    assert db_session.scalar(select(func.count(EvaluationCaseRecord.id))) == 1


def test_changed_published_catalog_is_rejected(
    db_session: Session,
    seeded_scope: tuple[uuid.UUID, uuid.UUID],
    tmp_path: Path,
) -> None:
    organization_id, project_id = seeded_scope
    original = _catalog(tmp_path / "catalog.json")
    import_catalog_artifact(
        db_session,
        organization_id=organization_id,
        project_id=project_id,
        artifact_path=original,
    )
    changed = _catalog(tmp_path / "changed.json", title="Changed title")
    with pytest.raises(VersionImportError, match="different immutable content"):
        import_catalog_artifact(
            db_session,
            organization_id=organization_id,
            project_id=project_id,
            artifact_path=changed,
        )


def test_dataset_requires_exact_catalog_products(
    db_session: Session,
    seeded_scope: tuple[uuid.UUID, uuid.UUID],
    tmp_path: Path,
) -> None:
    organization_id, project_id = seeded_scope
    import_catalog_artifact(
        db_session,
        organization_id=organization_id,
        project_id=project_id,
        artifact_path=_catalog(tmp_path / "catalog.json"),
    )
    with pytest.raises(VersionImportError, match="missing from catalog"):
        import_dataset_artifact(
            db_session,
            organization_id=organization_id,
            project_id=project_id,
            artifact_path=_dataset(tmp_path / "dataset.json", product_id="MISSING"),
        )


def test_cross_tenant_catalog_reference_is_rejected(
    db_session: Session,
    seeded_scope: tuple[uuid.UUID, uuid.UUID],
    second_scope: tuple[uuid.UUID, uuid.UUID],
    tmp_path: Path,
) -> None:
    organization_id, project_id = seeded_scope
    second_organization_id, second_project_id = second_scope
    import_catalog_artifact(
        db_session,
        organization_id=organization_id,
        project_id=project_id,
        artifact_path=_catalog(tmp_path / "catalog.json"),
    )
    with pytest.raises(VersionImportError, match="Referenced catalog"):
        import_dataset_artifact(
            db_session,
            organization_id=second_organization_id,
            project_id=second_project_id,
            artifact_path=_dataset(tmp_path / "dataset.json"),
        )


def test_source_validated_catalog_hash_must_match(
    db_session: Session,
    seeded_scope: tuple[uuid.UUID, uuid.UUID],
    tmp_path: Path,
) -> None:
    organization_id, project_id = seeded_scope
    catalog = import_catalog_artifact(
        db_session,
        organization_id=organization_id,
        project_id=project_id,
        artifact_path=_catalog(tmp_path / "catalog.json"),
    )
    version = db_session.get(CatalogVersionRecord, catalog.version_id)
    assert version is not None
    assert version.status == "PUBLISHED"
    assert version.artifact_hash == catalog.artifact_hash

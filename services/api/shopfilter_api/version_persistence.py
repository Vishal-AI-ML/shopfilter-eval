from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.esci_pipeline.review import (
    SourceValidatedDataset,
    compute_source_validated_hash,
)
from packages.evaluation_engine.datasets import (
    GoldenDataset,
    ReviewStatus,
    compute_dataset_hash,
)
from packages.evaluation_engine.models import Catalog
from services.api.shopfilter_api.models import (
    CatalogRecord,
    CatalogVersionRecord,
    DatasetRecord,
    DatasetVersionRecord,
    EvaluationCaseRecord,
    Organization,
    ProductRecord,
    Project,
)


class VersionImportError(ValueError):
    """Raised when immutable catalog or dataset content cannot be imported safely."""


@dataclass(frozen=True)
class VersionImportSummary:
    resource_id: uuid.UUID
    version_id: uuid.UUID
    external_id: str
    version: str
    created: bool
    item_count: int
    content_hash: str
    artifact_hash: str


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _artifact_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: str | Path) -> tuple[Path, dict[str, Any], str]:
    artifact_path = Path(path)
    try:
        raw = json.loads(artifact_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise TypeError("root must be an object")
        return artifact_path, raw, _artifact_hash(artifact_path)
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise VersionImportError(f"Unable to read JSON artifact: {artifact_path}") from exc


def _validate_length(value: str, label: str, maximum: int) -> None:
    if not value.strip() or len(value) > maximum:
        raise VersionImportError(f"{label} must contain 1 to {maximum} characters")


def _validate_catalog_limits(catalog: Catalog) -> None:
    _validate_length(catalog.catalog_id, "Catalog ID", 200)
    _validate_length(catalog.version, "Catalog version", 100)
    if not catalog.products:
        raise VersionImportError("Published catalog must contain at least one product")
    for product in catalog.products:
        _validate_length(product.product_id, "Product ID", 200)
        _validate_length(product.title, "Product title", 1000)


def _validate_dataset_limits(dataset: GoldenDataset | SourceValidatedDataset) -> None:
    _validate_length(dataset.dataset_id, "Dataset ID", 200)
    _validate_length(dataset.version, "Dataset version", 100)
    _validate_length(dataset.catalog_id, "Catalog ID", 200)
    _validate_length(dataset.catalog_version, "Catalog version", 100)
    if not dataset.cases:
        raise VersionImportError("Published dataset must contain at least one case")
    for case in dataset.cases:
        _validate_length(case.case_id, "Case ID", 200)
        _validate_length(case.query, "Case query", 2000)


def _require_scope(
    session: Session, organization_id: uuid.UUID, project_id: uuid.UUID
) -> None:
    if session.get(Organization, organization_id) is None:
        raise VersionImportError("Organization not found")
    project = session.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == organization_id,
        )
    )
    if project is None:
        raise VersionImportError("Project not found in organization")


def _existing_summary(
    resource: CatalogRecord | DatasetRecord,
    version: CatalogVersionRecord | DatasetVersionRecord,
    *,
    content_hash: str,
    artifact_hash: str,
) -> VersionImportSummary:
    if version.content_hash != content_hash or version.artifact_hash != artifact_hash:
        raise VersionImportError(
            "Published ID and version already exist with different immutable content"
        )
    return VersionImportSummary(
        resource_id=resource.id,
        version_id=version.id,
        external_id=resource.external_id or resource.name,
        version=version.version,
        created=False,
        item_count=version.item_count,
        content_hash=content_hash,
        artifact_hash=artifact_hash,
    )


def import_catalog_artifact(
    session: Session,
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    artifact_path: str | Path,
) -> VersionImportSummary:
    _require_scope(session, organization_id, project_id)
    _, raw, artifact_hash = _load_json(artifact_path)
    try:
        catalog = Catalog.model_validate(raw)
    except ValidationError as exc:
        raise VersionImportError("Catalog schema validation failed") from exc
    _validate_catalog_limits(catalog)
    content_hash = _canonical_hash(catalog.model_dump(mode="json"))
    resource = session.scalar(
        select(CatalogRecord).where(
            CatalogRecord.organization_id == organization_id,
            CatalogRecord.project_id == project_id,
            CatalogRecord.external_id == catalog.catalog_id,
        )
    )
    if resource is None:
        resource = CatalogRecord(
            organization_id=organization_id,
            project_id=project_id,
            name=catalog.catalog_id,
            external_id=catalog.catalog_id,
        )
        session.add(resource)
        session.flush()
    version = session.scalar(
        select(CatalogVersionRecord).where(
            CatalogVersionRecord.organization_id == organization_id,
            CatalogVersionRecord.catalog_id == resource.id,
            CatalogVersionRecord.version == catalog.version,
        )
    )
    if version is not None:
        return _existing_summary(
            resource, version, content_hash=content_hash, artifact_hash=artifact_hash
        )
    version = CatalogVersionRecord(
        organization_id=organization_id,
        catalog_id=resource.id,
        version=catalog.version,
        status="PUBLISHED",
        content_hash=content_hash,
        artifact_hash=artifact_hash,
        item_count=len(catalog.products),
        provenance={
            "artifact_filename": Path(artifact_path).name,
            "hash_algorithm": "sha256",
        },
    )
    session.add(version)
    session.flush()
    session.add_all(
        ProductRecord(
            organization_id=organization_id,
            catalog_version_id=version.id,
            product_id=product.product_id,
            title=product.title,
            payload=product.model_dump(mode="json"),
        )
        for product in catalog.products
    )
    session.commit()
    return VersionImportSummary(
        resource_id=resource.id,
        version_id=version.id,
        external_id=catalog.catalog_id,
        version=catalog.version,
        created=True,
        item_count=len(catalog.products),
        content_hash=content_hash,
        artifact_hash=artifact_hash,
    )


def _validated_dataset(raw: dict[str, Any]) -> GoldenDataset | SourceValidatedDataset:
    try:
        if raw.get("status") == "SOURCE_VALIDATED":
            source_validated = SourceValidatedDataset.model_validate(raw)
            if (
                compute_source_validated_hash(source_validated)
                != source_validated.content_hash
            ):
                raise VersionImportError("Dataset content hash does not match its contents")
            return source_validated
        golden = GoldenDataset.model_validate(raw)
        if golden.status != ReviewStatus.APPROVED:
            raise VersionImportError("Only published datasets can be imported")
        if compute_dataset_hash(golden) != golden.content_hash:
            raise VersionImportError("Dataset content hash does not match its contents")
        return golden
    except ValidationError as exc:
        raise VersionImportError("Dataset schema validation failed") from exc


def import_dataset_artifact(
    session: Session,
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    artifact_path: str | Path,
) -> VersionImportSummary:
    _require_scope(session, organization_id, project_id)
    _, raw, artifact_hash = _load_json(artifact_path)
    dataset = _validated_dataset(raw)
    _validate_dataset_limits(dataset)
    catalog = session.scalar(
        select(CatalogRecord).where(
            CatalogRecord.organization_id == organization_id,
            CatalogRecord.project_id == project_id,
            CatalogRecord.external_id == dataset.catalog_id,
        )
    )
    if catalog is None:
        raise VersionImportError("Referenced catalog is not imported in this project")
    catalog_version = session.scalar(
        select(CatalogVersionRecord).where(
            CatalogVersionRecord.organization_id == organization_id,
            CatalogVersionRecord.catalog_id == catalog.id,
            CatalogVersionRecord.version == dataset.catalog_version,
            CatalogVersionRecord.status == "PUBLISHED",
        )
    )
    if catalog_version is None:
        raise VersionImportError("Referenced published catalog version was not found")
    if (
        isinstance(dataset, SourceValidatedDataset)
        and catalog_version.artifact_hash != dataset.source_catalog_hash
    ):
        raise VersionImportError("Source-validated dataset catalog hash does not match")
    product_ids = set(
        session.scalars(
            select(ProductRecord.product_id).where(
                ProductRecord.organization_id == organization_id,
                ProductRecord.catalog_version_id == catalog_version.id,
            )
        ).all()
    )
    missing = sorted(
        {
            expected.product_id
            for case in dataset.cases
            for expected in case.expected_products
            if expected.product_id not in product_ids
        }
    )
    if missing:
        raise VersionImportError(
            f"Dataset references products missing from catalog: {', '.join(missing[:5])}"
        )
    resource = session.scalar(
        select(DatasetRecord).where(
            DatasetRecord.organization_id == organization_id,
            DatasetRecord.project_id == project_id,
            DatasetRecord.external_id == dataset.dataset_id,
        )
    )
    if resource is None:
        resource = DatasetRecord(
            organization_id=organization_id,
            project_id=project_id,
            name=dataset.dataset_id,
            external_id=dataset.dataset_id,
        )
        session.add(resource)
        session.flush()
    version = session.scalar(
        select(DatasetVersionRecord).where(
            DatasetVersionRecord.organization_id == organization_id,
            DatasetVersionRecord.dataset_id == resource.id,
            DatasetVersionRecord.version == dataset.version,
        )
    )
    if version is not None:
        return _existing_summary(
            resource,
            version,
            content_hash=dataset.content_hash,
            artifact_hash=artifact_hash,
        )
    provenance: dict[str, Any] = {
        key: raw[key]
        for key in (
            "source_manifest_id",
            "source_draft_hash",
            "source_catalog_hash",
            "validation_evidence",
        )
        if key in raw
    }
    provenance.update(
        {"artifact_filename": Path(artifact_path).name, "hash_algorithm": "sha256"}
    )
    version = DatasetVersionRecord(
        organization_id=organization_id,
        dataset_id=resource.id,
        catalog_version_id=catalog_version.id,
        version=dataset.version,
        status=dataset.status.value if isinstance(dataset, GoldenDataset) else dataset.status,
        content_hash=dataset.content_hash,
        artifact_hash=artifact_hash,
        item_count=len(dataset.cases),
        provenance=provenance,
    )
    session.add(version)
    session.flush()
    session.add_all(
        EvaluationCaseRecord(
            organization_id=organization_id,
            dataset_version_id=version.id,
            case_id=case.case_id,
            query=case.query,
            payload=case.model_dump(mode="json"),
        )
        for case in dataset.cases
    )
    session.commit()
    return VersionImportSummary(
        resource_id=resource.id,
        version_id=version.id,
        external_id=dataset.dataset_id,
        version=dataset.version,
        created=True,
        item_count=len(dataset.cases),
        content_hash=dataset.content_hash,
        artifact_hash=artifact_hash,
    )

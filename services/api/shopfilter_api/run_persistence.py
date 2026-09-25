
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.evaluation_engine.runner import EvaluationRunArtifact
from services.api.shopfilter_api.ai_systems import (
    AISystemStatus,
    AISystemType,
    AISystemVersionStatus,
    canonical_ai_system_version_hash,
    legacy_search_capabilities,
)
from services.api.shopfilter_api.artifact_storage import (
    ArtifactStorage,
    content_addressed_run_key,
)
from services.api.shopfilter_api.models import (
    CaseResultRecord,
    EvaluationRunRecord,
    FailureRecord,
    MetricResultRecord,
    Organization,
    Project,
    SearchSystemRecord,
    SearchSystemVersionRecord,
)


class RunImportError(ValueError):
    """Raised when an evaluation artifact cannot be persisted safely."""


@dataclass(frozen=True)
class RunImportSummary:
    evaluation_run_id: uuid.UUID
    external_run_id: str
    created: bool
    case_count: int
    metric_count: int
    failure_count: int
    artifact_uri: str


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_run_artifact(path: str | Path) -> tuple[EvaluationRunArtifact, str]:
    artifact_path = Path(path)
    try:
        artifact = EvaluationRunArtifact.model_validate_json(
            artifact_path.read_text(encoding="utf-8")
        )
        return artifact, _file_hash(artifact_path)
    except OSError as exc:
        raise RunImportError(f"Unable to read evaluation artifact: {artifact_path}") from exc
    except ValueError as exc:
        raise RunImportError("Evaluation artifact schema validation failed") from exc


def _require_scope(
    session: Session, organization_id: uuid.UUID, project_id: uuid.UUID
) -> None:
    if session.get(Organization, organization_id) is None:
        raise RunImportError("Organization not found")
    project = session.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == organization_id,
        )
    )
    if project is None:
        raise RunImportError("Project not found in organization")


def _search_system_version(
    session: Session,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    artifact: EvaluationRunArtifact,
) -> SearchSystemVersionRecord:
    system = session.scalar(
        select(SearchSystemRecord).where(
            SearchSystemRecord.organization_id == organization_id,
            SearchSystemRecord.project_id == project_id,
            SearchSystemRecord.name == artifact.adapter_provider,
        )
    )
    if system is None:
        system = SearchSystemRecord(
            organization_id=organization_id,
            project_id=project_id,
            name=artifact.adapter_provider,
            provider=artifact.adapter_provider,
            system_type=AISystemType.LEXICAL_SEARCH.value,
            status=AISystemStatus.ACTIVE.value,
        )
        session.add(system)
        session.flush()
    version = session.scalar(
        select(SearchSystemVersionRecord).where(
            SearchSystemVersionRecord.organization_id == organization_id,
            SearchSystemVersionRecord.search_system_id == system.id,
            SearchSystemVersionRecord.version == artifact.search_system_version,
        )
    )
    if version is None:
        configuration = {"adapter_provider": artifact.adapter_provider}
        capabilities = legacy_search_capabilities()
        version = SearchSystemVersionRecord(
            organization_id=organization_id,
            search_system_id=system.id,
            version=artifact.search_system_version,
            configuration=configuration,
            capabilities=capabilities,
            status=AISystemVersionStatus.PUBLISHED.value,
            content_hash=canonical_ai_system_version_hash(
                version=artifact.search_system_version,
                configuration=configuration,
                capabilities=capabilities,
            ),
        )
        session.add(version)
        session.flush()
    return version


def import_run_artifact(
    session: Session,
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    artifact_path: str | Path,
    artifact_storage: ArtifactStorage,
) -> RunImportSummary:
    _require_scope(session, organization_id, project_id)
    artifact, artifact_hash = load_run_artifact(artifact_path)
    existing = session.scalar(
        select(EvaluationRunRecord).where(
            EvaluationRunRecord.organization_id == organization_id,
            EvaluationRunRecord.external_run_id == artifact.run_id,
        )
    )
    if existing is not None:
        if (
            existing.result_fingerprint != artifact.result_fingerprint
            or existing.artifact_hash != artifact_hash
        ):
            raise RunImportError("Run ID already exists with different immutable content")
        stored = artifact_storage.put_verified(
            Path(artifact_path),
            object_key=content_addressed_run_key(
                organization_id=str(organization_id),
                project_id=str(project_id),
                sha256=artifact_hash,
            ),
            expected_sha256=artifact_hash,
        )
        if existing.artifact_uri != stored.uri:
            if existing.artifact_uri and not existing.artifact_uri.startswith("file://"):
                raise RunImportError("Run artifact URI does not match immutable object storage")
            existing.artifact_uri = stored.uri
            session.commit()
        metric_count = session.scalar(
            select(func.count(MetricResultRecord.id))
            .join(CaseResultRecord)
            .where(CaseResultRecord.evaluation_run_id == existing.id)
        ) or 0
        failure_count = session.scalar(
            select(func.count(FailureRecord.id))
            .join(CaseResultRecord)
            .where(CaseResultRecord.evaluation_run_id == existing.id)
        ) or 0
        return RunImportSummary(
            evaluation_run_id=existing.id,
            external_run_id=existing.external_run_id,
            created=False,
            case_count=existing.case_count,
            metric_count=metric_count,
            failure_count=failure_count,
            artifact_uri=stored.uri,
        )

    system_version = _search_system_version(
        session, organization_id, project_id, artifact
    )
    stored = artifact_storage.put_verified(
        Path(artifact_path),
        object_key=content_addressed_run_key(
            organization_id=str(organization_id),
            project_id=str(project_id),
            sha256=artifact_hash,
        ),
        expected_sha256=artifact_hash,
    )
    run = EvaluationRunRecord(
        organization_id=organization_id,
        project_id=project_id,
        search_system_version_id=system_version.id,
        external_run_id=artifact.run_id,
        result_fingerprint=artifact.result_fingerprint,
        artifact_hash=artifact_hash,
        artifact_uri=stored.uri,
        status="COMPLETED" if artifact.failed_case_count == 0 else "COMPLETED_WITH_ERRORS",
        dataset_id=artifact.dataset_id,
        dataset_version=artifact.dataset_version,
        dataset_hash=artifact.dataset_hash,
        catalog_id=artifact.catalog_id,
        catalog_version=artifact.catalog_version,
        adapter_provider=artifact.adapter_provider,
        trace_provider=artifact.trace_provider,
        metric_definition_version=artifact.metric_definition_version,
        top_k=artifact.top_k,
        seed=artifact.seed,
        case_count=artifact.case_count,
        passed_case_count=artifact.passed_case_count,
        failed_case_count=artifact.failed_case_count,
        aggregate_metrics=artifact.aggregate_metrics,
        failure_counts=artifact.failure_counts,
    )
    session.add(run)
    session.flush()
    metric_count = 0
    failure_count = 0
    for case in artifact.cases:
        case_record = CaseResultRecord(
            organization_id=organization_id,
            evaluation_run_id=run.id,
            case_id=case.case_id,
            query=case.query,
            expected_product_ids=case.expected_product_ids,
            actual_product_ids=case.actual_product_ids,
            false_positives=case.false_positives,
            false_negatives=case.false_negatives,
            trace_id=case.trace_id,
            trace_url=case.trace_url,
            passed=case.passed,
        )
        session.add(case_record)
        session.flush()
        for metric in case.metrics:
            session.add(
                MetricResultRecord(
                    organization_id=organization_id,
                    case_result_id=case_record.id,
                    metric_name=metric.metric_name,
                    metric_type=metric.metric_type.value,
                    value=metric.value,
                    passed=metric.passed,
                    evidence=metric.evidence.model_dump(mode="json"),
                    explanation=metric.explanation,
                )
            )
            metric_count += 1
        for failure in case.failures:
            session.add(
                FailureRecord(
                    organization_id=organization_id,
                    case_result_id=case_record.id,
                    failure_type=failure.failure_type.value,
                    severity=failure.severity,
                    component=failure.component,
                    confidence=failure.confidence,
                    status=failure.status,
                    evidence=failure.evidence.model_dump(mode="json"),
                    notes=failure.notes,
                )
            )
            failure_count += 1
    session.commit()
    return RunImportSummary(
        evaluation_run_id=run.id,
        external_run_id=run.external_run_id,
        created=True,
        case_count=run.case_count,
        metric_count=metric_count,
        failure_count=failure_count,
        artifact_uri=stored.uri,
    )

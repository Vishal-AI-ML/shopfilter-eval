from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.demo_search.engine import DemoSearchEngine
from packages.esci_pipeline.review import (
    SourceValidatedCase,
    SourceValidatedDataset,
)
from packages.evaluation_engine.datasets import GoldenCase, GoldenDataset, ReviewStatus
from packages.evaluation_engine.models import Catalog, Product
from packages.evaluation_engine.runner import (
    EvaluationCancelled,
    EvaluationRunner,
    write_run_artifact,
)
from packages.search_adapters.demo import DemoSearchAdapter
from services.api.shopfilter_api.artifact_storage import MinioArtifactStorage
from services.api.shopfilter_api.config import ApiSettings
from services.api.shopfilter_api.database import Database
from services.api.shopfilter_api.job_lifecycle import EvaluationJobStatus
from services.api.shopfilter_api.models import (
    CatalogRecord,
    CatalogVersionRecord,
    DatasetRecord,
    DatasetVersionRecord,
    EvaluationCaseRecord,
    EvaluationJobRecord,
    ProductRecord,
    SearchSystemRecord,
    SearchSystemVersionRecord,
    WorkerHeartbeatRecord,
)
from services.api.shopfilter_api.run_persistence import import_run_artifact
from services.worker.source_validated_runner import SourceValidatedEvaluationRunner


@dataclass(frozen=True)
class ExecutionOutcome:
    requeue: bool = False
    retry_delay_seconds: int = 0


@dataclass(frozen=True)
class LoadedJob:
    job_id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    top_k: int
    seed: int
    catalog: Catalog
    dataset: GoldenDataset | SourceValidatedDataset
    search_system_version: str


def _claim_job(database: Database, job_id: uuid.UUID, worker_id: str) -> bool:
    with database.session() as session:
        job = session.scalar(
            select(EvaluationJobRecord)
            .where(EvaluationJobRecord.id == job_id)
            .with_for_update()
        )
        if job is None or job.status != EvaluationJobStatus.QUEUED.value:
            return False
        now = datetime.now(UTC)
        if job.cancel_requested:
            job.status = EvaluationJobStatus.CANCELLED.value
            job.finished_at = now
            session.commit()
            return False
        job.status = EvaluationJobStatus.RUNNING.value
        job.attempt_count += 1
        job.started_at = job.started_at or now
        job.heartbeat_at = now
        heartbeat = session.get(WorkerHeartbeatRecord, worker_id)
        if heartbeat is not None:
            heartbeat.current_job_id = job.id
            heartbeat.last_seen_at = now
        session.commit()
        return True


def _load_job(session: Session, job_id: uuid.UUID) -> LoadedJob:
    job = session.get(EvaluationJobRecord, job_id)
    if job is None:
        raise RuntimeError("Evaluation job disappeared")
    dataset_version = session.get(DatasetVersionRecord, job.dataset_version_id)
    search_version = session.get(
        SearchSystemVersionRecord, job.search_system_version_id
    )
    if dataset_version is None or search_version is None:
        raise RuntimeError("Evaluation job input version is unavailable")
    dataset_record = session.get(DatasetRecord, dataset_version.dataset_id)
    search_system = session.get(SearchSystemRecord, search_version.search_system_id)
    if dataset_record is None or search_system is None:
        raise RuntimeError("Evaluation job input resource is unavailable")
    if dataset_record.project_id != job.project_id or search_system.project_id != job.project_id:
        raise RuntimeError("Evaluation job inputs do not share a project")
    if search_system.provider not in {"demo", "shopfilter-demo"}:
        raise RuntimeError("Search-system provider is not supported by this worker")
    if dataset_version.catalog_version_id is None:
        raise RuntimeError("Dataset version has no catalog version")
    catalog_version = session.get(
        CatalogVersionRecord, dataset_version.catalog_version_id
    )
    if catalog_version is None:
        raise RuntimeError("Catalog version is unavailable")
    catalog_record = session.get(CatalogRecord, catalog_version.catalog_id)
    if catalog_record is None:
        raise RuntimeError("Catalog is unavailable")
    product_rows = session.scalars(
        select(ProductRecord)
        .where(
            ProductRecord.organization_id == job.organization_id,
            ProductRecord.catalog_version_id == catalog_version.id,
        )
        .order_by(ProductRecord.product_id)
    ).all()
    catalog = Catalog(
        catalog_id=catalog_record.external_id or catalog_record.name,
        version=catalog_version.version,
        products=[Product.model_validate(row.payload) for row in product_rows],
    )
    case_rows = session.scalars(
        select(EvaluationCaseRecord)
        .where(
            EvaluationCaseRecord.organization_id == job.organization_id,
            EvaluationCaseRecord.dataset_version_id == dataset_version.id,
        )
        .order_by(EvaluationCaseRecord.case_id)
    ).all()
    dataset_id = dataset_record.external_id or dataset_record.name
    if dataset_version.content_hash is None:
        raise RuntimeError("Dataset version has no content hash")
    if dataset_version.status == "APPROVED":
        dataset: GoldenDataset | SourceValidatedDataset = GoldenDataset(
            dataset_id=dataset_id,
            version=dataset_version.version,
            catalog_id=catalog.catalog_id,
            catalog_version=catalog.version,
            status=ReviewStatus.APPROVED,
            cases=[GoldenCase.model_validate(row.payload) for row in case_rows],
            content_hash=dataset_version.content_hash,
        )
    elif dataset_version.status == "SOURCE_VALIDATED":
        provenance = dataset_version.provenance
        dataset = SourceValidatedDataset(
            dataset_id=dataset_id,
            version=dataset_version.version,
            catalog_id=catalog.catalog_id,
            catalog_version=catalog.version,
            source_manifest_id=str(provenance["source_manifest_id"]),
            source_draft_hash=str(provenance["source_draft_hash"]),
            source_catalog_hash=str(provenance["source_catalog_hash"]),
            validation_evidence=dict(provenance["validation_evidence"]),
            cases=[SourceValidatedCase.model_validate(row.payload) for row in case_rows],
            content_hash=dataset_version.content_hash,
        )
    else:
        raise RuntimeError("Dataset version is not published")
    return LoadedJob(
        job_id=job.id,
        organization_id=job.organization_id,
        project_id=job.project_id,
        top_k=job.top_k,
        seed=job.seed,
        catalog=catalog,
        dataset=dataset,
        search_system_version=search_version.version,
    )


def _cancel_requested(database: Database, job_id: uuid.UUID) -> bool:
    with database.session() as session:
        job = session.get(EvaluationJobRecord, job_id)
        return job is None or job.cancel_requested


def _record_progress(
    database: Database,
    job_id: uuid.UUID,
    worker_id: str,
    completed: int,
    total: int,
) -> None:
    with database.session() as session:
        job = session.get(EvaluationJobRecord, job_id)
        if job is None or job.status != EvaluationJobStatus.RUNNING.value:
            return
        now = datetime.now(UTC)
        job.completed_case_count = completed
        job.total_case_count = total
        job.heartbeat_at = now
        heartbeat = session.get(WorkerHeartbeatRecord, worker_id)
        if heartbeat is not None:
            heartbeat.last_seen_at = now
            heartbeat.current_job_id = job.id
        session.commit()


def _finish_cancelled(database: Database, job_id: uuid.UUID, worker_id: str) -> None:
    with database.session() as session:
        job = session.get(EvaluationJobRecord, job_id)
        if job is not None and job.status == EvaluationJobStatus.RUNNING.value:
            job.status = EvaluationJobStatus.CANCELLED.value
            job.cancel_requested = True
            job.finished_at = datetime.now(UTC)
        heartbeat = session.get(WorkerHeartbeatRecord, worker_id)
        if heartbeat is not None:
            heartbeat.current_job_id = None
        session.commit()


def _finish_failed(
    database: Database,
    job_id: uuid.UUID,
    worker_id: str,
    error_code: str,
) -> ExecutionOutcome:
    with database.session() as session:
        job = session.get(EvaluationJobRecord, job_id)
        if job is None:
            return ExecutionOutcome()
        heartbeat = session.get(WorkerHeartbeatRecord, worker_id)
        if heartbeat is not None:
            heartbeat.current_job_id = None
        job.error_code = error_code[:100]
        job.error_detail = "Worker execution failed"
        if job.cancel_requested:
            job.status = EvaluationJobStatus.CANCELLED.value
            job.finished_at = datetime.now(UTC)
            session.commit()
            return ExecutionOutcome()
        if job.attempt_count < job.max_attempts:
            job.status = EvaluationJobStatus.QUEUED.value
            job.dispatched_at = None
            session.commit()
            return ExecutionOutcome(
                requeue=True,
                retry_delay_seconds=min(2 ** job.attempt_count, 30),
            )
        job.status = EvaluationJobStatus.FAILED.value
        job.finished_at = datetime.now(UTC)
        session.commit()
        return ExecutionOutcome()


def _finish_completed(
    database: Database,
    job_id: uuid.UUID,
    worker_id: str,
    evaluation_run_id: uuid.UUID,
    failed_case_count: int,
) -> None:
    with database.session() as session:
        job = session.get(EvaluationJobRecord, job_id)
        if job is None:
            raise RuntimeError("Evaluation job disappeared before completion")
        job.evaluation_run_id = evaluation_run_id
        job.status = (
            EvaluationJobStatus.COMPLETED.value
            if failed_case_count == 0
            else EvaluationJobStatus.COMPLETED_WITH_ERRORS.value
        )
        job.completed_case_count = job.total_case_count
        job.finished_at = datetime.now(UTC)
        job.error_code = None
        job.error_detail = None
        heartbeat = session.get(WorkerHeartbeatRecord, worker_id)
        if heartbeat is not None:
            heartbeat.current_job_id = None
        session.commit()


def execute_job(
    database: Database,
    settings: ApiSettings,
    job_id: uuid.UUID,
    worker_id: str,
) -> ExecutionOutcome:
    if not _claim_job(database, job_id, worker_id):
        return ExecutionOutcome()
    try:
        with database.session() as session:
            loaded = _load_job(session, job_id)
        adapter = DemoSearchAdapter(DemoSearchEngine(loaded.catalog))
        def progress(completed: int, total: int) -> None:
            _record_progress(database, job_id, worker_id, completed, total)

        def cancelled() -> bool:
            return _cancel_requested(database, job_id)
        if isinstance(loaded.dataset, SourceValidatedDataset):
            source_runner = SourceValidatedEvaluationRunner(adapter, loaded.catalog)
            artifact = asyncio.run(
                source_runner.run(
                    loaded.dataset,
                    search_system_version=loaded.search_system_version,
                    top_k=loaded.top_k,
                    seed=loaded.seed,
                    progress_callback=progress,
                    cancellation_check=cancelled,
                )
            )
        else:
            golden_runner = EvaluationRunner(adapter, loaded.catalog)
            artifact = asyncio.run(
                golden_runner.run(
                    loaded.dataset,
                    search_system_version=loaded.search_system_version,
                    top_k=loaded.top_k,
                    seed=loaded.seed,
                    progress_callback=progress,
                    cancellation_check=cancelled,
                )
            )
        if cancelled():
            raise EvaluationCancelled("Evaluation cancellation requested")
        storage = MinioArtifactStorage(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_bucket,
            secure=settings.minio_secure,
        )
        with TemporaryDirectory(prefix="shopfilter-worker-") as directory:
            artifact_path = write_run_artifact(artifact, Path(directory))
            with database.session() as session:
                summary = import_run_artifact(
                    session,
                    organization_id=loaded.organization_id,
                    project_id=loaded.project_id,
                    artifact_path=artifact_path,
                    artifact_storage=storage,
                )
        _finish_completed(
            database,
            job_id,
            worker_id,
            summary.evaluation_run_id,
            artifact.failed_case_count,
        )
        return ExecutionOutcome()
    except EvaluationCancelled:
        _finish_cancelled(database, job_id, worker_id)
        return ExecutionOutcome()
    except Exception as exc:  # noqa: BLE001 - worker containment boundary
        return _finish_failed(
            database,
            job_id,
            worker_id,
            type(exc).__name__,
        )

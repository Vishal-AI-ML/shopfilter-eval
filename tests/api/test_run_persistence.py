from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from packages.evaluation_engine.models import (
    Failure,
    FailureEvidence,
    FailureType,
    MetricEvidence,
    MetricResult,
    MetricType,
)
from packages.evaluation_engine.runner import (
    CaseEvaluationResult,
    EvaluationRunArtifact,
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
from services.api.shopfilter_api.run_persistence import (
    RunImportError,
    import_run_artifact,
)


def _artifact() -> EvaluationRunArtifact:
    metric = MetricResult(
        metric_name="precision_at_10",
        metric_type=MetricType.DETERMINISTIC,
        value=0.5,
        passed=False,
        evidence=MetricEvidence(observed={"relevant": 1}),
    )
    failure = Failure(
        failure_type=FailureType.RANKING_FAILURE,
        severity="medium",
        component="ranking",
        confidence=0.9,
        evidence=FailureEvidence(observed_facts=["Relevant result was displaced"]),
    )
    case = CaseEvaluationResult(
        case_id="CASE-001",
        query="red running shoes",
        expected_product_ids=["p1"],
        actual_product_ids=["p2"],
        false_positives=["p2"],
        false_negatives=["p1"],
        metrics=[metric],
        failures=[failure],
        passed=False,
    )
    return EvaluationRunArtifact(
        run_id="run-test-001",
        result_fingerprint="f" * 64,
        dataset_id="golden-v1",
        dataset_version="v1",
        dataset_hash="d" * 64,
        catalog_id="demo-catalog",
        catalog_version="v1",
        search_system_version="healthy-v1",
        adapter_provider="shopfilter-demo",
        trace_provider="noop",
        metric_definition_version="deterministic-v1",
        top_k=10,
        seed=0,
        case_count=1,
        passed_case_count=0,
        failed_case_count=1,
        aggregate_metrics={"precision_at_10": 0.5},
        failure_counts={"RANKING_FAILURE": 1},
        cases=[case],
    )


def test_artifact_import_is_complete_idempotent_and_immutable(
    api_client, tmp_path: Path
) -> None:
    database = api_client.app.state.database
    with database.session() as session:
        organization = Organization(name="Import Org", slug="import-org")
        session.add(organization)
        session.flush()
        project = Project(
            organization_id=organization.id,
            name="Import Project",
            slug="import-project",
        )
        session.add(project)
        session.commit()
        organization_id = organization.id
        project_id = project.id

    artifact_path = tmp_path / "run.json"
    artifact_path.write_text(_artifact().model_dump_json(indent=2), encoding="utf-8")
    with database.session() as session:
        first = import_run_artifact(
            session,
            organization_id=organization_id,
            project_id=project_id,
            artifact_path=artifact_path,
        )
    with database.session() as session:
        second = import_run_artifact(
            session,
            organization_id=organization_id,
            project_id=project_id,
            artifact_path=artifact_path,
        )
        assert first.created is True
        assert second.created is False
        assert second.evaluation_run_id == first.evaluation_run_id
        assert session.scalar(select(func.count(EvaluationRunRecord.id))) == 1
        assert session.scalar(select(func.count(CaseResultRecord.id))) == 1
        assert session.scalar(select(func.count(MetricResultRecord.id))) == 1
        assert session.scalar(select(func.count(FailureRecord.id))) == 1
        assert session.scalar(select(func.count(SearchSystemRecord.id))) == 1
        assert session.scalar(select(func.count(SearchSystemVersionRecord.id))) == 1

    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["aggregate_metrics"]["precision_at_10"] = 0.75
    artifact_path.write_text(json.dumps(payload), encoding="utf-8")
    with database.session() as session, pytest.raises(
        RunImportError, match="different immutable content"
    ):
        import_run_artifact(
            session,
            organization_id=organization_id,
            project_id=project_id,
            artifact_path=artifact_path,
        )

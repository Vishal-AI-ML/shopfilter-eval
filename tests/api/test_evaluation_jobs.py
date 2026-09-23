from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from services.api.shopfilter_api.job_queue import InMemoryJobQueue
from services.api.shopfilter_api.models import (
    DatasetVersionRecord,
    EvaluationJobRecord,
)
from services.worker.job_executor import _finish_failed
from services.worker.main import recover_stale_jobs


def _setup_inputs(client: TestClient) -> tuple[dict[str, str], dict[str, str]]:
    organization = client.post(
        "/v1/organizations",
        json={"name": "Jobs Organization", "slug": "jobs-organization"},
    ).json()
    headers = {"X-Organization-ID": organization["id"]}
    project = client.post(
        "/v1/projects",
        headers=headers,
        json={"name": "Jobs Project", "slug": "jobs-project"},
    ).json()
    dataset = client.post(
        "/v1/datasets",
        headers=headers,
        json={"name": "Jobs Dataset", "project_id": project["id"]},
    ).json()
    with Session(client.app.state.database.engine) as session:
        dataset_version = DatasetVersionRecord(
            organization_id=uuid.UUID(organization["id"]),
            dataset_id=uuid.UUID(dataset["id"]),
            version="v1",
            status="PUBLISHED",
            content_hash="a" * 64,
            artifact_hash="b" * 64,
            item_count=200,
            provenance={"review_status": "SOURCE_VALIDATED"},
        )
        session.add(dataset_version)
        session.commit()
        dataset_version_id = str(dataset_version.id)
    search_system = client.post(
        "/v1/search-systems",
        headers=headers,
        json={"name": "Jobs Demo", "provider": "demo", "project_id": project["id"]},
    ).json()
    search_version = client.post(
        f"/v1/search-systems/{search_system['id']}/versions",
        headers=headers,
        json={"version": "v1", "configuration": {}},
    ).json()
    return headers, {
        "project_id": project["id"],
        "dataset_version_id": dataset_version_id,
        "search_system_version_id": search_version["id"],
    }


def test_job_creation_is_durable_dispatched_and_idempotent(
    authenticated_client: TestClient,
) -> None:
    headers, identifiers = _setup_inputs(authenticated_client)
    body = {
        **identifiers,
        "idempotency_key": "run-jobs-v1",
        "top_k": 10,
        "seed": 42,
    }
    created = authenticated_client.post(
        "/v1/evaluation-jobs", headers=headers, json=body
    )
    assert created.status_code == 202, created.text
    payload = created.json()
    assert payload["status"] == "QUEUED"
    assert payload["completed_case_count"] == 0
    assert payload["total_case_count"] == 200
    assert payload["dispatched_at"] is not None
    queue = authenticated_client.app.state.job_queue
    assert isinstance(queue, InMemoryJobQueue)
    assert list(queue.job_ids) == [uuid.UUID(payload["id"])]

    repeated = authenticated_client.post(
        "/v1/evaluation-jobs", headers=headers, json=body
    )
    assert repeated.status_code == 202
    assert repeated.json()["id"] == payload["id"]
    assert list(queue.job_ids) == [uuid.UUID(payload["id"])]

    conflict = authenticated_client.post(
        "/v1/evaluation-jobs",
        headers=headers,
        json={**body, "top_k": 20},
    )
    assert conflict.status_code == 409


def test_queued_job_can_be_cancelled_and_terminal_cancel_is_rejected(
    authenticated_client: TestClient,
) -> None:
    headers, identifiers = _setup_inputs(authenticated_client)
    job = authenticated_client.post(
        "/v1/evaluation-jobs",
        headers=headers,
        json={**identifiers, "idempotency_key": "cancel-job"},
    ).json()
    cancelled = authenticated_client.post(
        f"/v1/evaluation-jobs/{job['id']}/cancel", headers=headers
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["cancel_requested"] is True
    assert cancelled.json()["finished_at"] is not None
    assert authenticated_client.post(
        f"/v1/evaluation-jobs/{job['id']}/cancel", headers=headers
    ).status_code == 409


def test_job_inputs_and_reads_are_tenant_scoped(
    authenticated_client: TestClient,
) -> None:
    first_headers, identifiers = _setup_inputs(authenticated_client)
    second = authenticated_client.post(
        "/v1/organizations",
        json={"name": "Other Jobs", "slug": "other-jobs"},
    ).json()
    second_headers = {"X-Organization-ID": second["id"]}
    hidden = authenticated_client.post(
        "/v1/evaluation-jobs",
        headers=second_headers,
        json={**identifiers, "idempotency_key": "cross-tenant"},
    )
    assert hidden.status_code == 404
    assert authenticated_client.get(
        "/v1/evaluation-jobs", headers=first_headers
    ).json() == []


def test_worker_failure_retries_then_becomes_terminal(
    authenticated_client: TestClient,
) -> None:
    headers, identifiers = _setup_inputs(authenticated_client)
    created = authenticated_client.post(
        "/v1/evaluation-jobs",
        headers=headers,
        json={
            **identifiers,
            "idempotency_key": "retry-job",
            "max_attempts": 2,
        },
    ).json()
    job_id = uuid.UUID(created["id"])
    with Session(authenticated_client.app.state.database.engine) as session:
        job = session.get(EvaluationJobRecord, job_id)
        assert job is not None
        job.status = "RUNNING"
        job.attempt_count = 1
        session.commit()

    retry = _finish_failed(
        authenticated_client.app.state.database,
        job_id,
        "worker-test",
        "TemporaryFailure",
    )
    assert retry.requeue is True
    assert retry.retry_delay_seconds == 2
    with Session(authenticated_client.app.state.database.engine) as session:
        job = session.get(EvaluationJobRecord, job_id)
        assert job is not None
        assert job.status == "QUEUED"
        assert job.error_detail == "Worker execution failed"
        job.status = "RUNNING"
        job.attempt_count = 2
        session.commit()

    terminal = _finish_failed(
        authenticated_client.app.state.database,
        job_id,
        "worker-test",
        "PermanentFailure",
    )
    assert terminal.requeue is False
    with Session(authenticated_client.app.state.database.engine) as session:
        job = session.get(EvaluationJobRecord, job_id)
        assert job is not None
        assert job.status == "FAILED"
        assert job.finished_at is not None


@pytest.mark.parametrize(
    ("attempt_count", "max_attempts", "cancel_requested", "expected", "requeued"),
    [
        (1, 3, False, "QUEUED", True),
        (3, 3, False, "FAILED", False),
        (1, 3, True, "CANCELLED", False),
    ],
)
def test_stale_running_job_recovery(
    authenticated_client: TestClient,
    attempt_count: int,
    max_attempts: int,
    cancel_requested: bool,
    expected: str,
    requeued: bool,
) -> None:
    headers, identifiers = _setup_inputs(authenticated_client)
    created = authenticated_client.post(
        "/v1/evaluation-jobs",
        headers=headers,
        json={
            **identifiers,
            "idempotency_key": f"stale-{expected.casefold()}",
            "max_attempts": max_attempts,
        },
    ).json()
    job_id = uuid.UUID(created["id"])
    with Session(authenticated_client.app.state.database.engine) as session:
        job = session.get(EvaluationJobRecord, job_id)
        assert job is not None
        job.status = "RUNNING"
        job.attempt_count = attempt_count
        job.cancel_requested = cancel_requested
        job.heartbeat_at = datetime.now(UTC) - timedelta(minutes=5)
        session.commit()

    recovered = recover_stale_jobs(
        authenticated_client.app.state.database, stale_after_seconds=30
    )
    assert (job_id in recovered) is requeued
    with Session(authenticated_client.app.state.database.engine) as session:
        job = session.get(EvaluationJobRecord, job_id)
        assert job is not None
        assert job.status == expected
        assert job.error_code == "WORKER_HEARTBEAT_STALE"
        assert job.error_detail == "Worker heartbeat expired"
        if expected in {"FAILED", "CANCELLED"}:
            assert job.finished_at is not None

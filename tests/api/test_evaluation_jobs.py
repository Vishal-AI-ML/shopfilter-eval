from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from services.api.shopfilter_api.job_queue import InMemoryJobQueue
from services.api.shopfilter_api.models import DatasetVersionRecord


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

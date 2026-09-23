from __future__ import annotations

import logging

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.shopfilter_api.models import AuthSessionRecord, UserRecord

TEST_USER_EMAIL = "api-owner@example.com"
TEST_USER_PASSWORD = "test-owner-password-123"


def test_auth_and_membership_responses_and_logs_exclude_secret_material(
    authenticated_client: TestClient, caplog
) -> None:
    caplog.set_level(logging.INFO)
    organization = authenticated_client.post(
        "/v1/organizations",
        json={"name": "Secret Safe", "slug": "secret-safe"},
    )
    headers = {"X-Organization-ID": organization.json()["id"]}
    me = authenticated_client.get("/v1/auth/me")
    members = authenticated_client.get("/v1/organization-members", headers=headers)
    assert me.status_code == members.status_code == 200

    raw_token = authenticated_client.cookies["shopfilter_session"]
    with Session(authenticated_client.app.state.database.engine) as session:
        user = session.scalar(select(UserRecord).where(UserRecord.email == TEST_USER_EMAIL))
        auth_session = session.scalar(select(AuthSessionRecord))
        assert user is not None and auth_session is not None
        forbidden_values = {
            TEST_USER_PASSWORD,
            user.password_hash,
            raw_token,
            auth_session.token_hash,
            authenticated_client.app.state.settings.database_url,
            authenticated_client.app.state.settings.minio_access_key,
            authenticated_client.app.state.settings.minio_secret_key,
        }

    response_text = f"{organization.text}\n{me.text}\n{members.text}"
    log_text = caplog.text
    for value in forbidden_values:
        assert value not in response_text
        assert value not in log_text
    for field_name in ("password_hash", "token_hash", "database_url", "minio_secret_key"):
        assert field_name not in response_text
        assert field_name not in log_text

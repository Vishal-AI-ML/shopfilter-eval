from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from services.api.shopfilter_api.app import create_app
from services.api.shopfilter_api.auth import hash_password
from services.api.shopfilter_api.config import ApiSettings
from services.api.shopfilter_api.database import Base
from services.api.shopfilter_api.models import UserRecord

TEST_USER_EMAIL = "api-owner@example.com"
TEST_USER_PASSWORD = "test-owner-password-123"


@pytest.fixture
def api_client(tmp_path: Path) -> Iterator[TestClient]:
    database_path = tmp_path / "api.sqlite3"
    settings = ApiSettings(
        DATABASE_URL=f"sqlite+pysqlite:///{database_path}", REDIS_URL=None
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.database.engine)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def authenticated_client(api_client: TestClient) -> TestClient:
    with Session(api_client.app.state.database.engine) as session:
        session.add(
            UserRecord(
                email=TEST_USER_EMAIL,
                display_name="API Owner",
                password_hash=hash_password(TEST_USER_PASSWORD),
                is_active=True,
            )
        )
        session.commit()
    response = api_client.post(
        "/v1/auth/login",
        json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return api_client


from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.api.shopfilter_api.app import create_app
from services.api.shopfilter_api.config import ApiSettings
from services.api.shopfilter_api.database import Base


@pytest.fixture
def api_client(tmp_path: Path) -> Iterator[TestClient]:
    database_path = tmp_path / "api.sqlite3"
    settings = ApiSettings(DATABASE_URL=f"sqlite+pysqlite:///{database_path}")
    app = create_app(settings)
    Base.metadata.create_all(app.state.database.engine)
    with TestClient(app) as client:
        yield client

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from services.api.shopfilter_api.models import Organization, Project
from services.api.shopfilter_api.version_persistence import import_catalog_artifact


def test_catalog_version_reads_are_tenant_scoped(
    api_client: TestClient, tmp_path: Path
) -> None:
    app = cast(FastAPI, api_client.app)
    engine = app.state.database.engine
    with Session(engine) as session:
        first = Organization(name="First", slug="first")
        second = Organization(name="Second", slug="second")
        session.add_all([first, second])
        session.flush()
        project = Project(
            organization_id=first.id, name="Search", slug="search"
        )
        session.add(project)
        session.commit()
        first_id = first.id
        second_id = second.id
        project_id = project.id

        path = tmp_path / "catalog.json"
        path.write_text(
            json.dumps(
                {
                    "catalog_id": "catalog-one",
                    "version": "v1",
                    "products": [
                        {
                            "product_id": "P-1",
                            "title": "Shoe",
                            "category": "shoes",
                            "price": "10",
                            "currency": "USD",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        summary = import_catalog_artifact(
            session,
            organization_id=first_id,
            project_id=project_id,
            artifact_path=path,
        )

    own = api_client.get(
        f"/v1/catalogs/{summary.resource_id}/versions",
        headers={"X-Organization-ID": str(first_id)},
    )
    assert own.status_code == 200
    assert own.json()[0]["artifact_hash"] == summary.artifact_hash
    assert own.json()[0]["item_count"] == 1

    hidden = api_client.get(
        f"/v1/catalogs/{summary.resource_id}/versions",
        headers={"X-Organization-ID": str(second_id)},
    )
    assert hidden.status_code == 404

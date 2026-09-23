from __future__ import annotations

import argparse
import uuid

from services.api.shopfilter_api.config import get_settings
from services.api.shopfilter_api.database import Database
from services.api.shopfilter_api.version_persistence import (
    VersionImportSummary,
    import_catalog_artifact,
    import_dataset_artifact,
)


def _print(label: str, summary: VersionImportSummary) -> None:
    print(f"{label}: {summary.external_id} / {summary.version}")
    print(f"Version UUID: {summary.version_id}")
    print(f"Created: {summary.created}")
    print(f"Items: {summary.item_count}")
    print(f"Content hash: {summary.content_hash}")
    print(f"Artifact hash: {summary.artifact_hash}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Persist immutable catalog and dataset versions"
    )
    parser.add_argument("--organization-id", required=True, type=uuid.UUID)
    parser.add_argument("--project-id", required=True, type=uuid.UUID)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--dataset")
    arguments = parser.parse_args()
    database = Database(get_settings().database_url)
    try:
        with database.session() as session:
            catalog = import_catalog_artifact(
                session,
                organization_id=arguments.organization_id,
                project_id=arguments.project_id,
                artifact_path=arguments.catalog,
            )
            _print("Catalog", catalog)
            if arguments.dataset:
                dataset = import_dataset_artifact(
                    session,
                    organization_id=arguments.organization_id,
                    project_id=arguments.project_id,
                    artifact_path=arguments.dataset,
                )
                _print("Dataset", dataset)
    finally:
        database.dispose()


if __name__ == "__main__":
    main()

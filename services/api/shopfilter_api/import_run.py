
from __future__ import annotations

import argparse
import uuid

from services.api.shopfilter_api.config import get_settings
from services.api.shopfilter_api.database import Database
from services.api.shopfilter_api.run_persistence import import_run_artifact


def main() -> None:
    parser = argparse.ArgumentParser(description="Persist an immutable evaluation artifact")
    parser.add_argument("--organization-id", required=True, type=uuid.UUID)
    parser.add_argument("--project-id", required=True, type=uuid.UUID)
    parser.add_argument("--artifact", required=True)
    arguments = parser.parse_args()
    database = Database(get_settings().database_url)
    try:
        with database.session() as session:
            summary = import_run_artifact(
                session,
                organization_id=arguments.organization_id,
                project_id=arguments.project_id,
                artifact_path=arguments.artifact,
            )
    finally:
        database.dispose()
    print(f"Evaluation run: {summary.evaluation_run_id}")
    print(f"External run ID: {summary.external_run_id}")
    print(f"Created: {summary.created}")
    print(f"Cases: {summary.case_count}")
    print(f"Metrics: {summary.metric_count}")
    print(f"Failures: {summary.failure_count}")


if __name__ == "__main__":
    main()


# API and persistence foundation

Phase 14 introduces a tenant-aware FastAPI service backed by PostgreSQL. Authentication and role-based authorization are intentionally deferred to Phase 15; until then every project, catalog, and dataset request requires `X-Organization-ID` and every query filters by that tenant identifier.

## Local database

```powershell
docker compose -f infrastructure/docker/compose.yml up -d postgres minio
uv run alembic upgrade head
uv run python -m services.api.shopfilter_api.seed
uv run uvicorn services.api.shopfilter_api.app:app --reload
```

OpenAPI is available at `http://127.0.0.1:8000/docs`. Liveness and database readiness are exposed at `/health/live` and `/health/ready`.

## Initial persisted hierarchy

```text
Organization
└── Project
    ├── Catalog
    │   └── CatalogVersion
    │       └── Product
    └── Dataset
        └── DatasetVersion
            └── EvaluationCase
```

All tenant-owned rows carry `organization_id` even when it can be reached through a parent. This deliberate denormalization enables explicit tenant filters and later database security policies. Foreign keys preserve hierarchy; tenant-isolation tests verify that cross-organization project IDs cannot be used to create catalogs or datasets.

## Evaluation evidence persistence

The second Phase 14 increment persists search-system identities and immutable evaluation evidence:

```text
SearchSystem
└── SearchSystemVersion
    └── EvaluationRun
        └── CaseResult
            ├── MetricResult
            └── Failure (including evidence JSON)
```

Import a local immutable run artifact into the seeded tenant:

```powershell
uv run python -m services.api.shopfilter_api.import_run `
  --organization-id e5150000-0000-4000-8000-000000000001 `
  --project-id e5150000-0000-4000-8000-000000000002 `
  --artifact artifacts/runs/<run-id>.json
```

The import is idempotent for identical bytes and fingerprints. Reusing a run ID with different immutable content is rejected. Search-system records are created from normalized adapter/provider metadata. Tenant-scoped read APIs expose search systems, versions, evaluation summaries and run details without exposing data from another organization.

## Immutable catalog and dataset versions

Published catalog and dataset JSON artifacts are validated before persistence. The importer
stores both a canonical content hash and the SHA-256 of the exact source bytes. Re-importing
identical bytes is idempotent; reusing an external ID/version with different immutable content
is rejected. Dataset import requires the exact published catalog version and verifies every
referenced product. `SOURCE_VALIDATED` evidence is retained as provenance and is not described
as human review.

```powershell
uv run alembic upgrade head
uv run python -m services.api.shopfilter_api.import_versions `
  --organization-id e5150000-0000-4000-8000-000000000001 `
  --project-id e5150000-0000-4000-8000-000000000002 `
  --catalog data\processed\esci-en-v1-p10000\catalog.json `
  --dataset data\goldens\esci-golden-v1-source-validated.json
```

Tenant-scoped metadata endpoints:

- `GET /v1/catalogs/{catalog_id}/versions`
- `GET /v1/catalogs/{catalog_id}/versions/{version_id}`
- `GET /v1/datasets/{dataset_id}/versions`
- `GET /v1/datasets/{dataset_id}/versions/{version_id}`

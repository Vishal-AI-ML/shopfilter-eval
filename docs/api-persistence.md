
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

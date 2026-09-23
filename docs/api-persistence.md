
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

## MinIO-backed immutable run artifacts

Evaluation JSON bytes are stored under a tenant/project-scoped, content-addressed object key.
PostgreSQL remains the queryable system of record and stores the verified SHA-256 plus an
`s3://` URI; large artifact payloads are not copied into relational columns. The importer reads
the object back after upload and rejects any checksum mismatch. Re-importing an existing run
verifies the object again, and legacy `file://` metadata is promoted to the verified MinIO URI.

Configuration:

```text
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=shopfilter
MINIO_SECRET_KEY=shopfilter-dev-only
MINIO_SECURE=false
MINIO_BUCKET=shopfilter-artifacts
```

## Authentication foundation

Phase 15 uses Argon2id password hashes and opaque, revocable server-side sessions. The raw
session token is sent only as an HttpOnly SameSite cookie; PostgreSQL stores its SHA-256 digest.
Login returns one generic credential error to avoid disclosing whether an email exists. There is
no public registration endpoint. An initial owner is created from a password environment
variable so the secret is not exposed in shell history or process arguments.

```powershell
uv run python -m services.api.shopfilter_api.bootstrap_owner `
  --email owner@example.com `
  --display-name "Demo Owner" `
  --organization-slug shopfilter-demo
```

Authentication endpoints:

- `POST /v1/auth/login`
- `POST /v1/auth/logout`
- `GET /v1/auth/me`

The temporary `X-Organization-ID` boundary remains only during the authentication-foundation
increment. The next Phase 15 increment validates the authenticated user's membership and role
before any organization-scoped read or write.

## Authenticated organization context and RBAC

`X-Organization-ID` is now only a tenant selector, not an identity credential. Every scoped
request first validates the opaque login session and then requires a membership linking that user
to the selected organization. A forged or non-member organization ID returns 404 so tenant
existence is not disclosed.

Current permission matrix:

| Role | Read scoped resources | Create project/catalog/dataset/search system |
|---|---:|---:|
| OWNER | yes | yes |
| ADMIN | yes | yes |
| ENGINEER | yes | yes |
| REVIEWER | yes | no |
| VIEWER | yes | no |

Organization creation requires authentication and atomically grants the creator OWNER membership.
Health, readiness, OpenAPI and login remain public. Import CLIs are operator tools outside the HTTP
permission boundary and continue to require explicit organization/project identifiers.

## Membership governance and human dataset review

Phase 15 completes the HTTP authorization boundary with organization membership governance.
Owners and Admins can list members and add existing active users by normalized email. Admins can
manage Admin, Engineer, Reviewer and Viewer memberships but cannot create, change, demote or
remove an Owner. Only Owners can transfer ownership, and row locking plus a last-Owner check
prevents every removal or downgrade that would leave an organization without an Owner.
Engineer, Reviewer and Viewer roles cannot use membership-management endpoints.

Membership endpoints require the authenticated session and `X-Organization-ID`:

- `GET /v1/organization-members`
- `POST /v1/organization-members`
- `PATCH /v1/organization-members/{membership_id}`
- `DELETE /v1/organization-members/{membership_id}`

Human dataset decisions are append-only `DatasetReview` records rather than mutations to the
published dataset version. This preserves immutable dataset bytes and keeps automated
`SOURCE_VALIDATED` provenance distinct from human approval. Owners, Admins and Reviewers can
submit a review; Engineers and Viewers cannot. Any organization member can read review history.

- `GET /v1/datasets/{dataset_id}/versions/{version_id}/reviews`
- `POST /v1/datasets/{dataset_id}/versions/{version_id}/reviews`

| Role | Read resources | Create technical resources | Manage ordinary members | Manage Owners | Submit dataset review |
|---|---:|---:|---:|---:|---:|
| OWNER | yes | yes | yes | yes, with last-Owner protection | yes |
| ADMIN | yes | yes | yes | no | yes |
| ENGINEER | yes | yes | no | no | no |
| REVIEWER | yes | no | no | no | yes |
| VIEWER | yes | no | no | no | no |

API schemas expose only safe identity fields. Password hashes, session-token digests, raw session
cookies, database credentials and object-store credentials are not response fields and are covered
by automated non-disclosure assertions.

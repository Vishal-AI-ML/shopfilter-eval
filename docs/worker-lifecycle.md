# Evaluation worker and durable run lifecycle

Phase 16 moves long-running evaluations out of HTTP request processing. PostgreSQL is the durable
source of truth for job state; Redis carries wake-up notifications and is not the canonical job
database. This prevents a temporary Redis outage from deleting accepted work.

## Lifecycle

```text
QUEUED
├── RUNNING
├── CANCELLED
└── FAILED

RUNNING
├── COMPLETED
├── COMPLETED_WITH_ERRORS
├── FAILED
└── CANCELLED
```

Terminal states cannot transition. A queued cancellation becomes `CANCELLED` immediately. A
running cancellation sets `cancel_requested`; the executor will stop cooperatively at a safe case
boundary. Progress is stored as completed and total case counts, so status survives API or browser
restarts.

## Durable records

`evaluation_jobs` stores tenant scope, immutable input-version references, requester, idempotency
key, retry budget, progress, cancellation, heartbeat, safe error fields and the eventual immutable
evaluation-run reference. `(organization_id, idempotency_key)` is unique. Reusing a key with the
same request returns the existing job; reusing it for different inputs returns HTTP 409.

`worker_heartbeats` is operational state keyed by worker ID. It records the current job, last-seen
time and non-secret health metadata.

## Queue behavior

`POST /v1/evaluation-jobs` commits the job before publishing its UUID to Redis. If Redis is
unavailable, the durable `QUEUED` row remains recoverable for a later dispatcher or database poll.
The API never stores the job payload in Redis and never places credentials in queue messages.

Endpoints:

- `POST /v1/evaluation-jobs`
- `GET /v1/evaluation-jobs`
- `GET /v1/evaluation-jobs/{job_id}`
- `POST /v1/evaluation-jobs/{job_id}/cancel`

Owner, Admin and Engineer can enqueue or cancel. Reviewer and Viewer remain read-only. Every read
and mutation is organization-scoped.

## Local services

Docker Compose now includes persistent Redis and a worker container. The first Phase 16 increment
runs a database-backed worker heartbeat and establishes the durable queue boundary. The next
increment consumes jobs and executes the existing deterministic evaluation engine with progress,
retry and cooperative cancellation.

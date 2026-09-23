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

## Worker execution

The worker blocks on the Redis UUID queue and falls back to polling durable `QUEUED` rows when a
notification is missing. It atomically claims a row before execution, increments its attempt count,
and updates case progress plus heartbeats in PostgreSQL. Duplicate or stale Redis messages are
safe because only a `QUEUED` row can be claimed.

Published human-approved datasets use the full deterministic evaluator. `SOURCE_VALIDATED` ESCI
datasets use a relevance-only deterministic runner and retain explicit `human_reviewed: false`
trace metadata; they are never relabelled as human-reviewed. Both paths reconstruct the exact
catalog and dataset versions stored in PostgreSQL.

Cancellation is checked between cases. Retryable execution failures return the durable row to
`QUEUED` with bounded exponential backoff until `max_attempts`; the stored error detail remains
generic and secret-safe. Completion writes an immutable JSON artifact, verifies it in MinIO,
persists canonical run/case/metric evidence, links the job to the run, and transitions to
`COMPLETED` or `COMPLETED_WITH_ERRORS`.

## Crash recovery

Every running job carries a database heartbeat. A worker scans for stale `RUNNING` rows before
waiting on Redis. If the heartbeat expired, it clears the dead worker assignment and atomically:

- cancels a job whose cancellation was already requested;
- returns it to `QUEUED` when retry budget remains; or
- marks it `FAILED` when attempts are exhausted.

Recovery does not depend on the original Redis message. A retried evaluation restarts from the
first case, while persisted progress remains monotonic until the new attempt catches up. This is
at-least-once execution with idempotent immutable result persistence, not unsafe mid-case resume.

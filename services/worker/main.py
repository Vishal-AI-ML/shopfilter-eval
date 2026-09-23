from __future__ import annotations

import logging
import os
import socket
import time
import uuid
from datetime import UTC, datetime, timedelta

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import or_, select

from services.api.shopfilter_api.config import get_settings
from services.api.shopfilter_api.database import Database
from services.api.shopfilter_api.job_lifecycle import EvaluationJobStatus
from services.api.shopfilter_api.job_queue import QUEUE_KEY
from services.api.shopfilter_api.models import (
    EvaluationJobRecord,
    WorkerHeartbeatRecord,
)
from services.worker.job_executor import ExecutionOutcome, execute_job

logger = logging.getLogger(__name__)


def _record_heartbeat(
    database: Database, worker_id: str, *, redis_connected: bool
) -> None:
    with database.session() as session:
        heartbeat = session.get(WorkerHeartbeatRecord, worker_id)
        now = datetime.now(UTC)
        if heartbeat is None:
            heartbeat = WorkerHeartbeatRecord(
                worker_id=worker_id,
                current_job_id=None,
                last_seen_at=now,
                metadata_json={"redis_connected": redis_connected},
            )
            session.add(heartbeat)
        else:
            heartbeat.last_seen_at = now
            heartbeat.metadata_json = {"redis_connected": redis_connected}
        session.commit()


def _next_durable_job(database: Database) -> uuid.UUID | None:
    with database.session() as session:
        return session.scalar(
            select(EvaluationJobRecord.id)
            .where(EvaluationJobRecord.status == EvaluationJobStatus.QUEUED.value)
            .order_by(EvaluationJobRecord.created_at)
            .limit(1)
        )


def recover_stale_jobs(
    database: Database, *, stale_after_seconds: int
) -> list[uuid.UUID]:
    cutoff = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
    recovered: list[uuid.UUID] = []
    with database.session() as session:
        jobs = session.scalars(
            select(EvaluationJobRecord)
            .where(
                EvaluationJobRecord.status == EvaluationJobStatus.RUNNING.value,
                or_(
                    EvaluationJobRecord.heartbeat_at.is_(None),
                    EvaluationJobRecord.heartbeat_at < cutoff,
                ),
            )
            .order_by(EvaluationJobRecord.created_at)
            .with_for_update(skip_locked=True)
        ).all()
        now = datetime.now(UTC)
        for job in jobs:
            heartbeat = session.scalar(
                select(WorkerHeartbeatRecord).where(
                    WorkerHeartbeatRecord.current_job_id == job.id
                )
            )
            if heartbeat is not None:
                heartbeat.current_job_id = None
            job.error_code = "WORKER_HEARTBEAT_STALE"
            job.error_detail = "Worker heartbeat expired"
            if job.cancel_requested:
                job.status = EvaluationJobStatus.CANCELLED.value
                job.finished_at = now
            elif job.attempt_count < job.max_attempts:
                job.status = EvaluationJobStatus.QUEUED.value
                job.dispatched_at = None
                recovered.append(job.id)
            else:
                job.status = EvaluationJobStatus.FAILED.value
                job.finished_at = now
        session.commit()
    return recovered


def _mark_redispatched(database: Database, job_id: uuid.UUID) -> None:
    with database.session() as session:
        job = session.get(EvaluationJobRecord, job_id)
        if job is not None and job.status == EvaluationJobStatus.QUEUED.value:
            job.dispatched_at = datetime.now(UTC)
            session.commit()


def _requeue(
    redis_client: Redis,
    database: Database,
    job_id: uuid.UUID,
    outcome: ExecutionOutcome,
) -> None:
    if not outcome.requeue:
        return
    time.sleep(outcome.retry_delay_seconds)
    try:
        redis_client.rpush(QUEUE_KEY, str(job_id))
    except RedisError:
        logger.warning("Redis retry dispatch deferred", extra={"job_id": str(job_id)})
        return
    _mark_redispatched(database, job_id)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    if not settings.redis_url:
        raise SystemExit("REDIS_URL is required for the worker")
    worker_id = os.environ.get("WORKER_ID", socket.gethostname())
    database = Database(settings.database_url)
    redis_client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=settings.worker_heartbeat_seconds + 5,
    )
    logger.info("Evaluation worker started", extra={"worker_id": worker_id})
    try:
        while True:
            recovered = recover_stale_jobs(
                database,
                stale_after_seconds=settings.worker_stale_after_seconds,
            )
            redis_connected = False
            queued_job_id: uuid.UUID | None = recovered[0] if recovered else None
            try:
                redis_connected = bool(redis_client.ping())
                if queued_job_id is None:
                    message = redis_client.blpop(
                        [QUEUE_KEY], timeout=settings.worker_heartbeat_seconds
                    )
                    if message is not None:
                        raw_job_id = message[1]
                        if isinstance(raw_job_id, bytes):
                            raw_job_id = raw_job_id.decode("utf-8")
                        queued_job_id = uuid.UUID(raw_job_id)
            except (RedisError, ValueError):
                logger.warning("Redis queue receive failed", extra={"worker_id": worker_id})
            _record_heartbeat(
                database, worker_id, redis_connected=redis_connected
            )
            job_id = queued_job_id or _next_durable_job(database)
            if job_id is None:
                continue
            outcome = execute_job(database, settings, job_id, worker_id)
            _requeue(redis_client, database, job_id, outcome)
    except KeyboardInterrupt:
        logger.info("Evaluation worker stopped", extra={"worker_id": worker_id})
    finally:
        redis_client.close()
        database.dispose()


if __name__ == "__main__":
    main()

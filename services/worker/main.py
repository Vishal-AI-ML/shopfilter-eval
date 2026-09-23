from __future__ import annotations

import logging
import os
import socket
import time
from datetime import UTC, datetime

from redis import Redis
from redis.exceptions import RedisError

from services.api.shopfilter_api.config import get_settings
from services.api.shopfilter_api.database import Database
from services.api.shopfilter_api.models import WorkerHeartbeatRecord

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
        socket_timeout=5,
    )
    logger.info("Worker heartbeat service started", extra={"worker_id": worker_id})
    try:
        while True:
            redis_connected = False
            try:
                redis_connected = bool(redis_client.ping())
            except RedisError:
                logger.warning("Redis heartbeat failed", extra={"worker_id": worker_id})
            _record_heartbeat(
                database, worker_id, redis_connected=redis_connected
            )
            time.sleep(settings.worker_heartbeat_seconds)
    except KeyboardInterrupt:
        logger.info("Worker heartbeat service stopped", extra={"worker_id": worker_id})
    finally:
        redis_client.close()
        database.dispose()


if __name__ == "__main__":
    main()

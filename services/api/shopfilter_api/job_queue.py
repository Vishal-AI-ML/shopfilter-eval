from __future__ import annotations

import uuid
from collections import deque
from typing import Protocol

from redis import Redis
from redis.exceptions import RedisError

QUEUE_KEY = "shopfilter:evaluation-jobs"


class JobQueueUnavailable(RuntimeError):
    """Raised when Redis cannot accept a queue notification."""


class JobQueue(Protocol):
    def enqueue(self, job_id: uuid.UUID) -> None: ...

    def close(self) -> None: ...


class InMemoryJobQueue:
    def __init__(self) -> None:
        self.job_ids: deque[uuid.UUID] = deque()

    def enqueue(self, job_id: uuid.UUID) -> None:
        self.job_ids.append(job_id)

    def close(self) -> None:
        self.job_ids.clear()


class RedisJobQueue:
    def __init__(self, redis_url: str) -> None:
        self._client = Redis.from_url(redis_url, decode_responses=True)

    def enqueue(self, job_id: uuid.UUID) -> None:
        try:
            self._client.rpush(QUEUE_KEY, str(job_id))
        except RedisError as exc:
            raise JobQueueUnavailable("Evaluation queue is temporarily unavailable") from exc

    def close(self) -> None:
        self._client.close()

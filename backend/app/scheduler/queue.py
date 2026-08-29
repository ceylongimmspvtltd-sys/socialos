"""Publishing queue abstraction.

- `inproc` (default demo): asyncio-driven worker using the DB as the durable source
  of truth (scheduled_posts) + an in-memory delayed-retry registry.
- `redis`: Redis sorted-set transport (same interface) for BullMQ/Celery parity in
  horizontally-scaled deployments. Both feed the same worker logic.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.config import settings


@dataclass
class Job:
    id: str
    kind: str                     # publish | analytics_sync
    payload: dict = field(default_factory=dict)
    run_at: float = field(default_factory=time.time)
    attempts: int = 0


class QueueBackend(Protocol):
    async def enqueue(self, job: Job) -> None: ...
    async def due(self, now: float | None = None) -> list[Job]: ...
    async def defer(self, job: Job, delay_s: float) -> None: ...
    async def dead_letter(self, job: Job, reason: str) -> None: ...


class InProcessQueue:
    """Single-process broker: ready list + delayed heap + DLQ audit."""

    def __init__(self) -> None:
        self._ready: list[Job] = []
        self._delayed: list[tuple[float, int, Job]] = []
        self._seq = 0
        self.dlq: list[dict] = []
        self._lock = asyncio.Lock()

    async def enqueue(self, job: Job) -> None:
        async with self._lock:
            self._ready.append(job)

    async def due(self, now: float | None = None) -> list[Job]:
        now = now or time.time()
        async with self._lock:
            moved = [j for _, _, j in self._delayed if _ <= now]
            if moved:
                self._delayed = [t for t in self._delayed if t[2] not in moved]
                self._ready.extend(moved)
            jobs, self._ready = self._ready, []
            return [j for j in jobs if j.run_at <= now]

    async def defer(self, job: Job, delay_s: float) -> None:
        async with self._lock:
            self._seq += 1
            self._delayed.append((time.time() + delay_s, self._seq, job))

    async def dead_letter(self, job: Job, reason: str) -> None:
        self.dlq.append({"job": job.id, "kind": job.kind, "reason": reason,
                         "attempts": job.attempts, "at": time.time()})


class RedisQueue:
    """Sorted-set transport: zset `socialos:jobs` scored by run_at, DLQ stream."""

    def __init__(self, url: str | None = None):
        import redis.asyncio as aioredis  # lazy: optional dependency in demo mode

        self.r = aioredis.from_url(url or settings.redis_url)
        self.key = "socialos:jobs"
        self.dlq_key = "socialos:dlq"

    async def enqueue(self, job: Job) -> None:
        await self.r.zadd(self.key, {json.dumps({"id": job.id, "kind": job.kind, "payload": job.payload}): job.run_at})

    async def due(self, now: float | None = None) -> list[Job]:
        now = now or time.time()
        rows = await self.r.zrangebyscore(self.key, "-inf", now)
        jobs = [Job(id=j["id"], kind=j["kind"], payload=j["payload"]) for j in map(json.loads, rows)]
        if rows:
            await self.r.zremrangebyscore(self.key, "-inf", now)
        return jobs

    async def defer(self, job: Job, delay_s: float) -> None:
        job.run_at = time.time() + delay_s
        await self.enqueue(job)

    async def dead_letter(self, job: Job, reason: str) -> None:
        await self.r.xadd(self.dlq_key, {"id": job.id, "reason": reason, "attempts": job.attempts})


_queue: QueueBackend | None = None


def get_queue() -> QueueBackend:
    global _queue
    if _queue is None:
        _queue = RedisQueue() if settings.queue_backend == "redis" else InProcessQueue()
    return _queue


def reset_queue() -> None:
    global _queue
    _queue = None

"""The job runner — one GPU lane, DB-backed (PursuitAI ai_jobs shape, single machine).

enqueue_job → claim_job (FOR UPDATE SKIP LOCKED) → run_job (handler, heartbeat, progress) → done/failed
reap_stuck_jobs re-queues a job whose worker died (no heartbeat for `job_stale_seconds`) and FAILS it past max_attempts.
Handlers are registered per `kind`; they receive (session, job) and return a result dict or raise.

Every write here opens its OWN short session (so a crashed handler can't take the bookkeeping down with it) — tests must
redirect `async_session` to the test engine (conftest `_redirect_jobs_to_test_engine`).
"""
from __future__ import annotations

import asyncio
import contextvars
import logging
import socket
import traceback
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import database as db
from app.core.config import get_settings
from app.models import Job, JobStatus

log = logging.getLogger(__name__)
Handler = Callable[[AsyncSession, Job], Awaitable[dict]]
_HANDLERS: dict[str, Handler] = {}
current_job_id: contextvars.ContextVar[uuid.UUID | None] = contextvars.ContextVar("current_job_id", default=None)
WORKER_ID = f"{socket.gethostname()}:{uuid.uuid4().hex[:6]}"


def register_handler(kind: str, fn: Handler) -> None:
    _HANDLERS[kind] = fn


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def enqueue_job(session: AsyncSession, *, kind: str, payload: dict, user_id: uuid.UUID | None = None,
                      idempotency_key: str | None = None, stages: list[dict] | None = None) -> Job:
    """Idempotent on `idempotency_key` while a matching job is queued/running: returns the existing one."""
    if idempotency_key:
        existing = (await session.execute(select(Job).where(
            Job.idempotency_key == idempotency_key, Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING])))).scalar_one_or_none()
        if existing:
            return existing
    job = Job(kind=kind, payload=payload, user_id=user_id, idempotency_key=idempotency_key,
              max_attempts=get_settings().job_max_attempts,
              progress={"stages": stages or [], "current": "queued"} if stages else None)
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def claim_job(session: AsyncSession, kinds: list[str] | None = None) -> Job | None:
    """Atomically take the oldest queued job. SKIP LOCKED means two workers can never take the same one."""
    q = select(Job).where(Job.status == JobStatus.QUEUED).order_by(Job.created_at).limit(1).with_for_update(skip_locked=True)
    if kinds:
        q = q.where(Job.kind.in_(kinds))
    job = (await session.execute(q)).scalar_one_or_none()
    if job is None:
        return None
    job.status = JobStatus.RUNNING
    job.attempts += 1
    job.worker_id = WORKER_ID
    job.started_at = job.heartbeat_at = _now()
    await session.commit()
    await session.refresh(job)
    return job


async def heartbeat(job_id: uuid.UUID) -> None:
    async with db.async_session() as s:
        await s.execute(update(Job).where(Job.id == job_id).values(heartbeat_at=_now()))
        await s.commit()


async def report_progress(job_id: uuid.UUID, current: str) -> None:
    async with db.async_session() as s:
        job = await s.get(Job, job_id)
        if job:
            job.progress = {**(job.progress or {"stages": []}), "current": current}
            job.heartbeat_at = _now()
            await s.commit()


async def _finish(job_id: uuid.UUID, *, status: JobStatus, result: dict | None = None, error: str | None = None) -> None:
    async with db.async_session() as s:
        job = await s.get(Job, job_id)
        if not job:
            return
        job.status = status
        job.result = result
        job.error = error
        job.finished_at = _now()
        job.input_blob = None  # never keep uploads past a terminal state
        if job.progress:
            job.progress = {**job.progress, "current": "done" if status == JobStatus.DONE else "failed"}
        await s.commit()


async def run_job(job: Job) -> None:
    """Execute one claimed job to a terminal state. The handler must NOT set terminal state itself."""
    handler = _HANDLERS.get(job.kind)
    if handler is None:
        await _finish(job.id, status=JobStatus.FAILED, error=f"no handler for kind={job.kind}")
        return
    token = current_job_id.set(job.id)
    stop = asyncio.Event()

    async def _beat() -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=15)
            except asyncio.TimeoutError:
                try:
                    await heartbeat(job.id)
                except Exception:  # noqa: BLE001
                    log.exception("heartbeat failed")

    beat = asyncio.create_task(_beat())
    try:
        async with db.async_session() as s:
            job = await s.get(Job, job.id)
            result = await handler(s, job)
        await _finish(job.id, status=JobStatus.DONE, result=result)
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-1500:]}"
        log.error("job %s failed (attempt %s): %s", job.id, job.attempts, exc)
        async with db.async_session() as s:
            j = await s.get(Job, job.id)
            retry = j is not None and j.attempts < j.max_attempts
        if retry:
            async with db.async_session() as s:
                j = await s.get(Job, job.id)
                j.status = JobStatus.QUEUED
                j.error = err
                j.worker_id = None
                await s.commit()
        else:
            await _finish(job.id, status=JobStatus.FAILED, error=err)
    finally:
        stop.set()
        beat.cancel()
        current_job_id.reset(token)


async def reap_stuck_jobs() -> int:
    """Re-queue RUNNING jobs whose heartbeat went silent; fail those past max_attempts. Returns count touched."""
    stale = _now() - timedelta(seconds=get_settings().job_stale_seconds)
    async with db.async_session() as s:
        rows = (await s.execute(select(Job).where(Job.status == JobStatus.RUNNING, Job.heartbeat_at < stale))).scalars().all()
        for j in rows:
            if j.attempts >= j.max_attempts:
                j.status = JobStatus.FAILED
                j.error = (j.error or "") + "\nworker died (no heartbeat); attempts exhausted"
                j.finished_at = _now()
            else:
                j.status = JobStatus.QUEUED
                j.worker_id = None
                j.error = (j.error or "") + "\nworker died (no heartbeat); re-queued"
        await s.commit()
        return len(rows)


async def run_once(kinds: list[str] | None = None) -> bool:
    """Claim + run at most one job. Returns True if a job ran. Tests drive the lane with this."""
    async with db.async_session() as s:
        job = await claim_job(s, kinds)
    if job is None:
        return False
    await run_job(job)
    return True


async def worker_loop(stop: asyncio.Event) -> None:
    """The in-process single-lane worker started by the app lifespan."""
    poll = get_settings().job_poll_seconds
    n = 0
    while not stop.is_set():
        try:
            ran = await run_once()
            n += 1
            if n % 30 == 0:
                await reap_stuck_jobs()
        except Exception:  # noqa: BLE001
            log.exception("worker loop error")
            ran = False
        if not ran:
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll)
            except asyncio.TimeoutError:
                pass


async def db_ping() -> bool:
    async with db.async_session() as s:
        await s.execute(text("SELECT 1"))
    return True

"""Job runner invariants: SKIP LOCKED claim, heartbeat/reaper, idempotency, unknown kind."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import Job, JobStatus
from app.services import jobs


async def _noop(session, job):
    return {"ok": True, "payload": job.payload}


async def test_claim_is_fifo_and_single_claim(session):
    jobs.register_handler("noop", _noop)
    a = await jobs.enqueue_job(session, kind="noop", payload={"n": 1})
    b = await jobs.enqueue_job(session, kind="noop", payload={"n": 2})
    first = await jobs.claim_job(session)
    assert first.id == a.id and first.status == JobStatus.RUNNING and first.attempts == 1
    second = await jobs.claim_job(session)
    assert second.id == b.id
    assert await jobs.claim_job(session) is None


async def test_run_once_completes_with_result(session):
    jobs.register_handler("noop", _noop)
    j = await jobs.enqueue_job(session, kind="noop", payload={"x": 1}, stages=[{"key": "a", "label": "A"}])
    assert await jobs.run_once() is True
    await session.refresh(j)
    assert j.status == JobStatus.DONE and j.result == {"ok": True, "payload": {"x": 1}} and j.progress["current"] == "done"
    assert j.finished_at is not None


async def test_unknown_kind_fails_cleanly(session):
    j = await jobs.enqueue_job(session, kind="nope", payload={})
    await jobs.run_once()
    await session.refresh(j)
    assert j.status == JobStatus.FAILED and "no handler" in j.error


async def test_reaper_requeues_silent_worker_then_fails_past_max(session):
    jobs.register_handler("noop", _noop)
    j = await jobs.enqueue_job(session, kind="noop", payload={})
    j = await jobs.claim_job(session)  # now RUNNING with a fresh heartbeat
    assert await jobs.reap_stuck_jobs() == 0  # heartbeat is fresh
    j.heartbeat_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await session.commit()
    assert await jobs.reap_stuck_jobs() == 1
    await session.refresh(j)
    assert j.status == JobStatus.QUEUED and "worker died" in j.error and j.worker_id is None
    j.attempts = j.max_attempts
    j.status = JobStatus.RUNNING
    j.heartbeat_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await session.commit()
    assert await jobs.reap_stuck_jobs() == 1
    await session.refresh(j)
    assert j.status == JobStatus.FAILED


async def test_idempotency_key_dedupes_only_active(session):
    jobs.register_handler("noop", _noop)
    a = await jobs.enqueue_job(session, kind="noop", payload={}, idempotency_key="k1")
    b = await jobs.enqueue_job(session, kind="noop", payload={}, idempotency_key="k1")
    assert a.id == b.id
    await jobs.run_once()
    c = await jobs.enqueue_job(session, kind="noop", payload={}, idempotency_key="k1")
    assert c.id != a.id
    assert len((await session.execute(select(Job))).scalars().all()) == 2

"""Jobs: poll one, list recent. The web `useJob` hook polls GET /jobs/{id} until a terminal status."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import current_user
from app.core.database import get_db
from app.models import Job, JobStatus, User
from app.schemas import JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> JobOut:
    job = await session.get(Job, job_id)
    if job is None or (job.user_id is not None and job.user_id != user.id):
        raise HTTPException(404, "job not found")
    return JobOut.model_validate(job, from_attributes=True)


@router.get("", response_model=list[JobOut])
async def list_jobs(session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> list[JobOut]:
    rows = (await session.execute(select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc()).limit(50))).scalars().all()
    return [JobOut.model_validate(j, from_attributes=True) for j in rows]


@router.post("/{job_id}/cancel", response_model=JobOut)
async def cancel_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> JobOut:
    job = await session.get(Job, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(404, "job not found")
    if job.status == JobStatus.QUEUED:  # a running render can't be interrupted inside the engine; it just won't be retried
        job.status = JobStatus.CANCELLED
    elif job.status == JobStatus.RUNNING:
        job.max_attempts = job.attempts
    await session.commit()
    return JobOut.model_validate(job, from_attributes=True)

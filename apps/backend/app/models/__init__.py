"""Riff data model (Phase 1): users · songs · generations · jobs.

`user_id` is on every row from day one so multi-tenant (V2) is a migration, not a rewrite. V1 seeds ONE local user.
Remix tables (uploads / stems / remixes) arrive in Phase 4.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Index, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class SongStatus(str, enum.Enum):
    DRAFT = "draft"  # lyrics/brief only
    RENDERING = "rendering"
    READY = "ready"  # ≥1 generation
    FAILED = "failed"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str] = mapped_column(String(120), default="You")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Song(Base):
    __tablename__ = "songs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    keywords: Mapped[str | None] = mapped_column(Text)
    style: Mapped[str] = mapped_column(Text)  # the engine caption: genre, instruments, vocal, mood
    lyrics: Mapped[str | None] = mapped_column(Text)  # section-tagged; None/empty ⇒ instrumental
    brief: Mapped[dict | None] = mapped_column(JSON)  # Claude song brief (Phase 2): bpm/key/mood/structure/…
    bpm: Mapped[int | None] = mapped_column(Integer)
    key: Mapped[str | None] = mapped_column(String(24))
    vocal_language: Mapped[str] = mapped_column(String(8), default="en")
    duration_s: Mapped[int] = mapped_column(Integer, default=150)
    status: Mapped[SongStatus] = mapped_column(Enum(SongStatus, name="song_status"), default=SongStatus.DRAFT)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    generations: Mapped[list["Generation"]] = relationship(back_populates="song", cascade="all, delete-orphan")


class Generation(Base):
    """One rendered take. A generate request with `takes=2` produces two rows sharing `batch_id`."""

    __tablename__ = "generations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    song_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("songs.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=_uuid, index=True)
    take_index: Mapped[int] = mapped_column(Integer, default=1)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(80))
    seed: Mapped[str | None] = mapped_column(String(40))
    params: Mapped[dict] = mapped_column(JSON, default=dict)  # exactly what was sent to the engine
    metas: Mapped[dict | None] = mapped_column(JSON)  # what the engine reported (bpm/key/…)
    duration_s: Mapped[float | None] = mapped_column(Float)
    wav_path: Mapped[str] = mapped_column(String(500))  # relative to media_root
    mp3_path: Mapped[str | None] = mapped_column(String(500))
    lufs: Mapped[float | None] = mapped_column(Float)
    render_seconds: Mapped[float | None] = mapped_column(Float)
    is_favorite: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    song: Mapped[Song] = relationship(back_populates="generations")


class Job(Base):
    """The one GPU lane. Claimed with FOR UPDATE SKIP LOCKED; heartbeat + reaper mirror PursuitAI's ai_jobs."""

    __tablename__ = "jobs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)  # render | remix | analyze …
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus, name="job_status"), default=JobStatus.QUEUED, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(120))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    input_blob: Mapped[bytes | None] = mapped_column(LargeBinary)  # remix uploads (cleared at terminal state)
    progress: Mapped[dict | None] = mapped_column(JSON)  # {"stages":[{"key","label"}], "current": "rendering"}
    result: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    worker_id: Mapped[str | None] = mapped_column(String(80))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

    __table_args__ = (
        # one in-flight job per idempotency key (a double-click can't render twice)
        Index("ux_jobs_idem_active", "idempotency_key", unique=True,
              postgresql_where="status IN ('QUEUED','RUNNING')"),
    )

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


class UploadStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    FAILED = "failed"


class RemixMode(str, enum.Enum):
    REIMAGINE = "reimagine"  # Claude understands the song and writes a fresh ARRANGEMENT; the engine performs it (AI voice)
    REIMAGINE_KEEP = "reimagine_keep"  # same arrangement rendered INSTRUMENTAL at the original tempo + your real auto-tuned vocal
    HYBRID = "hybrid"  # real lead over an AI cover WITH backing vocals
    KEEP = "keep"  # real lead over a new instrumental bed
    RESING = "resing"  # the AI sings the transcribed lyrics
    INSTRUMENTAL = "instrumental"


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
    # Timings belong to an AUDIO, not to a song: two takes of the same lyric sing it differently, and a re-sung remix
    # differs again. Filled by the `align` job (Whisper on this file); null until someone asks for it.
    lyrics_segments: Mapped[list | None] = mapped_column(JSON)
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


class Upload(Base):
    """A song the user brought in (or promoted from a generation) to remix. Analysis = stems + tempo/key + lyrics."""

    __tablename__ = "uploads"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    filename: Mapped[str] = mapped_column(String(255))
    source_path: Mapped[str] = mapped_column(String(500))  # media-relative WAV (normalized copy of the upload)
    rights_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    from_generation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("generations.id", ondelete="SET NULL"))
    vocal_language: Mapped[str] = mapped_column(String(8), default="en")
    status: Mapped[UploadStatus] = mapped_column(Enum(UploadStatus, name="upload_status"), default=UploadStatus.UPLOADED)
    duration_s: Mapped[float | None] = mapped_column(Float)
    bpm: Mapped[float | None] = mapped_column(Float)
    key: Mapped[str | None] = mapped_column(String(24))
    lufs: Mapped[float | None] = mapped_column(Float)
    lyrics: Mapped[str | None] = mapped_column(Text)  # transcribed (Whisper), user-editable
    lyrics_segments: Mapped[list | None] = mapped_column(JSON)  # [{start, end, text}]
    analysis: Mapped[dict | None] = mapped_column(JSON)  # stem energy split, timings, tool versions
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    stems: Mapped[list["Stem"]] = relationship(back_populates="upload", cascade="all, delete-orphan")
    remixes: Mapped[list["Remix"]] = relationship(back_populates="upload", cascade="all, delete-orphan")


class Stem(Base):
    __tablename__ = "stems"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    upload_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("uploads.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # vocals | drums | bass | other | instrumental
    path: Mapped[str] = mapped_column(String(500))
    energy_share: Mapped[float | None] = mapped_column(Float)

    upload: Mapped[Upload] = relationship(back_populates="stems")


class Remix(Base):
    """One remix run of an upload. Output is a mastered WAV + MP3 like a Generation."""

    __tablename__ = "remixes"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    upload_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("uploads.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    mode: Mapped[RemixMode] = mapped_column(Enum(RemixMode, name="remix_mode"), default=RemixMode.HYBRID)
    preset_key: Mapped[str | None] = mapped_column(String(40))
    style: Mapped[str] = mapped_column(Text)  # the engine caption actually sent
    closeness: Mapped[float] = mapped_column(Float, default=0.45)
    bpm_to: Mapped[float | None] = mapped_column(Float)
    ai_forward: Mapped[int] = mapped_column(Integer, default=1)  # -3 (way back) … 4 (front)
    harmony: Mapped[str] = mapped_column(String(20), default="")  # opt-in; the lead stays clean by default
    chops: Mapped[bool] = mapped_column(default=False)
    autotune: Mapped[bool] = mapped_column(default=True)  # pitch-correct the real vocal to the song's key (default ON)
    autotune_strength: Mapped[float] = mapped_column(Float, default=0.85)  # 0 = untouched … 1 = hard snap
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=_uuid, index=True)  # one run = N variations
    take_index: Mapped[int] = mapped_column(Integer, default=1)
    direction: Mapped[str | None] = mapped_column(String(120))  # reimagine: "emotional ballad", "cinematic anthem", …
    # "fast" = turbo, 8 steps (seconds, for auditioning); "studio" = the SFT model at 50 steps (~6x slower,
    # noticeably more high-frequency detail). Stored per remix so a version says which model actually made it.
    quality: Mapped[str] = mapped_column(String(12), default="fast", server_default="fast")
    brief: Mapped[dict | None] = mapped_column(JSON)  # reimagine: Claude's reading — meaning, arc, structure, lyrics, caption
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued | rendering | ready | failed
    wav_path: Mapped[str | None] = mapped_column(String(500))
    mp3_path: Mapped[str | None] = mapped_column(String(500))
    lufs: Mapped[float | None] = mapped_column(Float)
    duration_s: Mapped[float | None] = mapped_column(Float)
    render_seconds: Mapped[float | None] = mapped_column(Float)
    seed: Mapped[str | None] = mapped_column(String(40))
    is_favorite: Mapped[bool] = mapped_column(default=False)
    lyrics_segments: Mapped[list | None] = mapped_column(JSON)  # see Generation.lyrics_segments
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    upload: Mapped[Upload] = relationship(back_populates="remixes")

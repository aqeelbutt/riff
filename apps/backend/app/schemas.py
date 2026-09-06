"""API request/response shapes."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models import JobStatus, SongStatus


class SongCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    style: str = Field(min_length=3, description="engine caption: genre, instruments, vocal, mood")
    lyrics: str | None = Field(default=None, description="section-tagged lyrics; empty ⇒ instrumental")
    keywords: str | None = None
    bpm: int | None = Field(default=None, ge=40, le=220)
    key: str | None = Field(default=None, max_length=24)
    vocal_language: str = Field(default="en", max_length=8)
    duration_s: int = Field(default=150, ge=10, le=600)


class SongUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    style: str | None = Field(default=None, min_length=3)
    lyrics: str | None = None
    bpm: int | None = Field(default=None, ge=40, le=220)
    key: str | None = Field(default=None, max_length=24)
    vocal_language: str | None = Field(default=None, max_length=8)
    duration_s: int | None = Field(default=None, ge=10, le=600)


class GenerateRequest(BaseModel):
    takes: int = Field(default=2, ge=1, le=8)
    quality: str = Field(default="fast", pattern="^(fast|studio)$")


class GenerationOut(BaseModel):
    id: uuid.UUID
    song_id: uuid.UUID
    batch_id: uuid.UUID
    take_index: int
    provider: str
    model: str | None
    seed: str | None
    metas: dict | None
    duration_s: float | None
    lufs: float | None
    render_seconds: float | None
    is_favorite: bool
    audio_url: str
    mp3_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SongOut(BaseModel):
    id: uuid.UUID
    title: str
    style: str
    lyrics: str | None
    keywords: str | None
    bpm: int | None
    key: str | None
    vocal_language: str
    duration_s: int
    status: SongStatus
    created_at: datetime
    updated_at: datetime
    generations: list[GenerationOut] = []

    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    id: uuid.UUID
    kind: str
    status: JobStatus
    progress: dict | None
    result: dict | None
    error: str | None
    attempts: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}

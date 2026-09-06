"""Songs: create a draft (style + lyrics), generate takes (async job), list, read, update."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import current_user
from app.core.database import get_db
from app.models import Generation, Song, User
from app.schemas import GenerateRequest, GenerationOut, JobOut, SongCreate, SongOut, SongUpdate
from app.services.generation import enqueue_render

router = APIRouter(prefix="/songs", tags=["songs"])


def _gen_out(g: Generation) -> GenerationOut:
    return GenerationOut(
        id=g.id, song_id=g.song_id, batch_id=g.batch_id, take_index=g.take_index, provider=g.provider, model=g.model,
        seed=g.seed, metas=g.metas, duration_s=g.duration_s, lufs=g.lufs, render_seconds=g.render_seconds,
        is_favorite=g.is_favorite, audio_url=f"/generations/{g.id}/audio", mp3_url=f"/generations/{g.id}/mp3" if g.mp3_path else None,
        created_at=g.created_at,
    )


def _song_out(s: Song) -> SongOut:
    fields = {k: getattr(s, k) for k in SongOut.model_fields if k != "generations"}
    return SongOut(**fields, generations=[_gen_out(g) for g in sorted(s.generations, key=lambda g: (g.created_at, g.take_index))])


async def _load(session: AsyncSession, song_id: uuid.UUID, user: User) -> Song:
    song = (await session.execute(
        select(Song).options(selectinload(Song.generations)).where(Song.id == song_id, Song.user_id == user.id))).scalar_one_or_none()
    if song is None:
        raise HTTPException(404, "song not found")
    return song


@router.post("", response_model=SongOut, status_code=201)
async def create_song(body: SongCreate, session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> SongOut:
    song = Song(user_id=user.id, **body.model_dump())
    session.add(song)
    await session.commit()
    return _song_out(await _load(session, song.id, user))


@router.get("", response_model=list[SongOut])
async def list_songs(session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> list[SongOut]:
    rows = (await session.execute(
        select(Song).options(selectinload(Song.generations)).where(Song.user_id == user.id).order_by(Song.created_at.desc()).limit(200)
    )).scalars().all()
    return [_song_out(s) for s in rows]


@router.get("/{song_id}", response_model=SongOut)
async def get_song(song_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> SongOut:
    return _song_out(await _load(session, song_id, user))


@router.patch("/{song_id}", response_model=SongOut)
async def update_song(song_id: uuid.UUID, body: SongUpdate, session: AsyncSession = Depends(get_db),
                      user: User = Depends(current_user)) -> SongOut:
    song = await _load(session, song_id, user)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(song, k, v)
    await session.commit()
    return _song_out(await _load(session, song_id, user))


@router.post("/{song_id}/generate", response_model=JobOut, status_code=202)
async def generate(song_id: uuid.UUID, body: GenerateRequest, session: AsyncSession = Depends(get_db),
                   user: User = Depends(current_user)) -> JobOut:
    song = await _load(session, song_id, user)
    job = await enqueue_render(session, song, takes=body.takes, quality=body.quality)
    return JobOut.model_validate(job, from_attributes=True)

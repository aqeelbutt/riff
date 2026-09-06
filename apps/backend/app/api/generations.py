"""Generations: stream audio, toggle favorite."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import current_user
from app.core.database import get_db
from app.models import Generation, User
from app.services.storage import get_storage

router = APIRouter(prefix="/generations", tags=["generations"])


async def _load(session: AsyncSession, gen_id: uuid.UUID, user: User) -> Generation:
    g = await session.get(Generation, gen_id)
    if g is None or g.user_id != user.id:
        raise HTTPException(404, "generation not found")
    return g


@router.get("/{gen_id}/audio")
async def audio(gen_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> FileResponse:
    g = await _load(session, gen_id, user)
    p = get_storage().absolute(g.wav_path)
    if not p.exists():
        raise HTTPException(410, "audio file is gone")
    return FileResponse(p, media_type="audio/wav", filename=f"{g.song_id}-take{g.take_index}.wav")


@router.get("/{gen_id}/mp3")
async def mp3(gen_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> FileResponse:
    g = await _load(session, gen_id, user)
    if not g.mp3_path:
        raise HTTPException(404, "no mp3 for this take")
    p = get_storage().absolute(g.mp3_path)
    if not p.exists():
        raise HTTPException(410, "audio file is gone")
    return FileResponse(p, media_type="audio/mpeg", filename=f"{g.song_id}-take{g.take_index}.mp3")


@router.post("/{gen_id}/favorite")
async def favorite(gen_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> dict:
    g = await _load(session, gen_id, user)
    g.is_favorite = not g.is_favorite
    await session.commit()
    return {"id": str(g.id), "is_favorite": g.is_favorite}


@router.delete("/{gen_id}", status_code=204)
async def delete_generation(gen_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> None:
    g = await _load(session, gen_id, user)
    st = get_storage()
    for rel in (g.wav_path, g.mp3_path):
        if rel:
            p = st.absolute(rel)
            if p.exists():
                p.unlink(missing_ok=True)
    await session.delete(g)
    await session.commit()

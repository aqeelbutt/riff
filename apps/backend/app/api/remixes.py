"""Remixes: list, read, stream, keep, delete."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.uploads import RemixOut, remix_out
from app.core.auth import current_user
from app.core.database import get_db
from app.models import Remix, User
from app.services.storage import get_storage

router = APIRouter(prefix="/remixes", tags=["remixes"])


async def _load(session: AsyncSession, rid: uuid.UUID, user: User) -> Remix:
    r = await session.get(Remix, rid)
    if r is None or r.user_id != user.id:
        raise HTTPException(404, "remix not found")
    return r


@router.get("", response_model=list[RemixOut])
async def list_remixes(session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> list[RemixOut]:
    rows = (await session.execute(select(Remix).where(Remix.user_id == user.id).order_by(Remix.created_at.desc()).limit(300))).scalars().all()
    return [remix_out(r) for r in rows]


@router.get("/{rid}", response_model=RemixOut)
async def get_remix(rid: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> RemixOut:
    return remix_out(await _load(session, rid, user))


def _file(r: Remix, rel: str | None, media: str, ext: str) -> FileResponse:
    if not rel:
        raise HTTPException(404, "not rendered yet")
    p = get_storage().absolute(rel)
    if not p.exists():
        raise HTTPException(410, "file is gone")
    return FileResponse(p, media_type=media, filename=f"remix-{r.id}{ext}")


@router.get("/{rid}/audio")
async def audio(rid: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> FileResponse:
    r = await _load(session, rid, user)
    return _file(r, r.wav_path, "audio/wav", ".wav")


@router.get("/{rid}/mp3")
async def mp3(rid: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> FileResponse:
    r = await _load(session, rid, user)
    return _file(r, r.mp3_path, "audio/mpeg", ".mp3")


@router.post("/{rid}/favorite")
async def favorite(rid: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> dict:
    r = await _load(session, rid, user)
    r.is_favorite = not r.is_favorite
    await session.commit()
    return {"id": str(r.id), "is_favorite": r.is_favorite}


@router.delete("/{rid}", status_code=204)
async def delete_remix(rid: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> None:
    r = await _load(session, rid, user)
    st = get_storage()
    for rel in (r.wav_path, r.mp3_path):
        if rel:
            p = st.absolute(rel)
            if p.exists():
                p.unlink(missing_ok=True)
    await session.delete(r)
    await session.commit()

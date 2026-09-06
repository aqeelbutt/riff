"""Uploads: bring a song in (file or one of your own takes), analyze it, fix its lyrics, stream its stems, remix it."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models import Generation, Remix, RemixMode, Song, Stem, Upload, User
from app.schemas import JobOut
from app.services.presets import REIMAGINE_DIRECTIONS, REMIX_PRESETS
from app.services.remix import delete_upload_files, enqueue_analyze, enqueue_remix, ffmpeg_to_wav
from app.services.storage import get_storage

router = APIRouter(prefix="/uploads", tags=["uploads"])
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".aiff", ".aif"}


class StemOut(BaseModel):
    kind: str
    energy_share: float | None
    audio_url: str


class RemixOut(BaseModel):
    id: uuid.UUID
    upload_id: uuid.UUID
    job_id: uuid.UUID | None
    batch_id: uuid.UUID
    take_index: int
    mode: RemixMode
    preset_key: str | None
    style: str
    closeness: float
    bpm_to: float | None
    ai_forward: int
    harmony: str
    chops: bool
    autotune: bool
    autotune_strength: float
    direction: str | None
    brief: dict | None
    params: dict
    status: str
    seed: str | None
    lufs: float | None
    duration_s: float | None
    render_seconds: float | None
    is_favorite: bool
    lyrics_segments: list | None
    error: str | None
    audio_url: str | None
    mp3_url: str | None
    created_at: datetime


class UploadOut(BaseModel):
    id: uuid.UUID
    title: str
    filename: str
    status: str
    vocal_language: str
    duration_s: float | None
    bpm: float | None
    key: str | None
    lufs: float | None
    lyrics: str | None
    lyrics_segments: list | None
    analysis: dict | None
    error: str | None
    from_generation_id: uuid.UUID | None
    audio_url: str
    stems: list[StemOut] = []
    remixes: list[RemixOut] = []
    created_at: datetime


class UploadPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    lyrics: str | None = Field(default=None, max_length=8000)
    vocal_language: str | None = Field(default=None, max_length=8)


class RemixIn(BaseModel):
    """`mode` decides which catalogue `preset_key` comes from: reimagine* → REIMAGINE_DIRECTIONS, otherwise REMIX_PRESETS."""

    preset_key: str | None = None
    style: str | None = Field(default=None, max_length=600, description="free-text style; overrides the preset caption")
    mode: RemixMode = RemixMode.HYBRID
    closeness: float = Field(default=0.45, ge=0.2, le=0.9)
    bpm_to: float | None = Field(default=None, ge=40, le=220)
    ai_forward: int = Field(default=1, ge=-3, le=4)
    harmony: str = Field(default="", pattern=r"^(-?\d{1,2}(,-?\d{1,2})*)?$")
    chops: bool = False
    autotune: bool = True
    autotune_strength: float = Field(default=0.85, ge=0, le=1)
    takes: int = Field(default=2, ge=1, le=4)
    moods: list[str] = Field(default_factory=list)
    direction: str | None = Field(default=None, max_length=120, description="reimagine only: how to arrange it, e.g. 'emotional ballad'")
    lyrics: str | None = Field(default=None, max_length=8000, description="use these lyrics for this run instead of the transcription")


def remix_out(r: Remix) -> RemixOut:
    return RemixOut(**{k: getattr(r, k) for k in RemixOut.model_fields if k not in ("audio_url", "mp3_url")},
                    audio_url=f"/remixes/{r.id}/audio" if r.wav_path else None, mp3_url=f"/remixes/{r.id}/mp3" if r.mp3_path else None)


def upload_out(u: Upload) -> UploadOut:
    fields = {k: getattr(u, k) for k in UploadOut.model_fields if k not in ("audio_url", "stems", "remixes", "status")}
    return UploadOut(**fields, status=u.status.value, audio_url=f"/uploads/{u.id}/audio",
                     stems=[StemOut(kind=s.kind, energy_share=s.energy_share, audio_url=f"/uploads/{u.id}/stems/{s.kind}") for s in u.stems],
                     remixes=[remix_out(r) for r in sorted(u.remixes, key=lambda r: (r.created_at, r.take_index), reverse=True)])


async def _load(session: AsyncSession, upload_id: uuid.UUID, user: User) -> Upload:
    u = (await session.execute(select(Upload).options(selectinload(Upload.stems), selectinload(Upload.remixes))
                               .where(Upload.id == upload_id, Upload.user_id == user.id))).scalar_one_or_none()
    if u is None:
        raise HTTPException(404, "upload not found")
    return u


def _safe_title(name: str) -> str:
    return re.sub(r"[_\-]+", " ", Path(name).stem).strip()[:120] or "Untitled"


@router.post("", response_model=dict, status_code=202)
async def create_upload(file: UploadFile = File(...), rights: bool = Form(...), vocal_language: str = Form("en"), title: str | None = Form(None),
                        session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> dict:
    """Multipart: file + rights=true (+ vocal_language, title). Stores a normalized WAV and queues the analysis job."""
    if not rights:
        raise HTTPException(422, "confirm you own this song or have the rights to remix it")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in AUDIO_EXT:
        raise HTTPException(415, f"unsupported audio type {ext or '(none)'}; use mp3, wav, m4a, flac, aac or ogg")
    st = get_storage()
    up = Upload(user_id=user.id, title=title or _safe_title(file.filename or "song"), filename=file.filename or "song", source_path="pending",
                rights_confirmed_at=datetime.now(timezone.utc), vocal_language=vocal_language)
    session.add(up)
    await session.flush()
    folder = st.root / "uploads" / str(up.id)
    folder.mkdir(parents=True, exist_ok=True)
    raw = folder / f"original{ext}"
    max_bytes = get_settings().upload_max_mb * 1024 * 1024
    size = 0
    with open(raw, "wb") as fh:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                fh.close(); raw.unlink(missing_ok=True); await session.rollback()
                raise HTTPException(413, f"file is over {get_settings().upload_max_mb} MB")
            fh.write(chunk)
    try:
        ffmpeg_to_wav(raw, folder / "source.wav")
    except RuntimeError as exc:
        await session.rollback()
        raise HTTPException(415, str(exc)) from exc
    up.source_path = st.relative(folder / "source.wav")
    await session.commit()
    job = await enqueue_analyze(session, up)
    return {"upload": upload_out(await _load(session, up.id, user)).model_dump(mode="json"), "job": JobOut.model_validate(job, from_attributes=True).model_dump(mode="json")}


@router.post("/from-generation/{gen_id}", response_model=dict, status_code=202)
async def upload_from_generation(gen_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> dict:
    """Remix one of your own takes — no rights question, it's yours."""
    g = await session.get(Generation, gen_id)
    if g is None or g.user_id != user.id:
        raise HTTPException(404, "take not found")
    song = await session.get(Song, g.song_id)
    st = get_storage()
    up = Upload(user_id=user.id, title=song.title if song else "Take", filename=f"{song.title if song else 'take'}.wav", source_path="pending",
                rights_confirmed_at=datetime.now(timezone.utc), vocal_language=song.vocal_language if song else "en", from_generation_id=g.id)
    session.add(up)
    await session.flush()
    folder = st.root / "uploads" / str(up.id)
    ffmpeg_to_wav(st.absolute(g.wav_path), folder / "source.wav")
    up.source_path = st.relative(folder / "source.wav")
    if song and song.lyrics:
        up.lyrics = song.lyrics  # we already know the words — Whisper only fills gaps
    await session.commit()
    job = await enqueue_analyze(session, up)
    return {"upload": upload_out(await _load(session, up.id, user)).model_dump(mode="json"), "job": JobOut.model_validate(job, from_attributes=True).model_dump(mode="json")}


@router.get("", response_model=list[UploadOut])
async def list_uploads(session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> list[UploadOut]:
    rows = (await session.execute(select(Upload).options(selectinload(Upload.stems), selectinload(Upload.remixes))
                                  .where(Upload.user_id == user.id).order_by(Upload.created_at.desc()).limit(200))).scalars().all()
    return [upload_out(u) for u in rows]


@router.get("/{upload_id}", response_model=UploadOut)
async def get_upload(upload_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> UploadOut:
    return upload_out(await _load(session, upload_id, user))


@router.patch("/{upload_id}", response_model=UploadOut)
async def patch_upload(upload_id: uuid.UUID, body: UploadPatch, session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> UploadOut:
    u = await _load(session, upload_id, user)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(u, k, v)
    await session.commit()
    return upload_out(await _load(session, upload_id, user))


@router.get("/{upload_id}/audio")
async def upload_audio(upload_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> FileResponse:
    u = await _load(session, upload_id, user)
    p = get_storage().absolute(u.source_path)
    if not p.exists():
        raise HTTPException(410, "source file is gone")
    return FileResponse(p, media_type="audio/wav", filename=f"{u.title}.wav")


@router.get("/{upload_id}/stems/{kind}")
async def stem_audio(upload_id: uuid.UUID, kind: str, session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> FileResponse:
    u = await _load(session, upload_id, user)
    s = next((s for s in u.stems if s.kind == kind), None)
    if s is None:
        raise HTTPException(404, "no such stem")
    p = get_storage().absolute(s.path)
    if not p.exists():
        raise HTTPException(410, "stem file is gone")
    return FileResponse(p, media_type="audio/wav", filename=f"{u.title}-{kind}.wav")


@router.post("/{upload_id}/remix", response_model=dict, status_code=202)
async def remix(upload_id: uuid.UUID, body: RemixIn, session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> dict:
    u = await _load(session, upload_id, user)
    if u.status.value != "analyzed":
        raise HTTPException(409, f"upload is {u.status.value}; wait for the analysis to finish")
    reimagining = body.mode.value.startswith("reimagine")
    catalogue = REIMAGINE_DIRECTIONS if reimagining else REMIX_PRESETS
    preset = next((p for p in catalogue if p["key"] == body.preset_key), None) if body.preset_key else None
    if body.preset_key and preset is None:
        raise HTTPException(422, "unknown preset")
    if reimagining and not (u.lyrics or "").strip():
        raise HTTPException(409, "no lyrics to work from — add them on the previous step, then reimagine")
    style = (body.style or (preset["caption"] if preset else None) or "").strip()
    if not style:
        raise HTTPException(422, "pick a preset or describe the style")
    if body.moods:
        style += ", " + ", ".join(m.lower() for m in body.moods)
    closeness = body.closeness if body.closeness != 0.45 or not preset else preset.get("closeness", 0.45)
    direction = (body.direction or (preset["label"] if preset else None) or body.style or "").strip()[:120] if reimagining else None
    rows, job = await enqueue_remix(session, u, mode=body.mode, style=style, preset_key=body.preset_key, closeness=closeness, bpm_to=body.bpm_to,
                                    ai_forward=body.ai_forward, harmony=body.harmony, chops=body.chops, autotune=body.autotune,
                                    autotune_strength=body.autotune_strength, takes=body.takes, lyrics_override=body.lyrics, direction=direction)
    return {"remixes": [remix_out(r).model_dump(mode="json") for r in rows], "job": JobOut.model_validate(job, from_attributes=True).model_dump(mode="json")}


@router.delete("/{upload_id}", status_code=204)
async def delete_upload(upload_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> None:
    u = await _load(session, upload_id, user)
    await session.delete(u)
    await session.commit()
    delete_upload_files(u)

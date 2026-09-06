"""The `render` job handler: Song → MusicProvider → mastering → Generation rows."""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Generation, Job, Song, SongStatus
from app.services import jobs
from app.services.mastering import master
from app.services.music import RenderRequest, get_provider
from app.services.storage import get_storage

RENDER_STAGES = [
    {"key": "queued", "label": "Queued"},
    {"key": "rendering", "label": "Composing"},
    {"key": "decoding", "label": "Decoding audio"},
    {"key": "mastering", "label": "Mastering"},
]


def _content_hash(song: Song) -> str:
    """What the engine would see. Same content in flight ⇒ same job (a double-click can't pay twice)."""
    raw = "|".join(str(x) for x in (song.style, song.lyrics, song.bpm, song.key, song.vocal_language, song.duration_s))
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


async def enqueue_render(session: AsyncSession, song: Song, *, takes: int = 2, quality: str = "fast") -> Job:
    batch_id = uuid.uuid4()
    job = await jobs.enqueue_job(
        session, kind="render", user_id=song.user_id, stages=RENDER_STAGES,
        idempotency_key=f"render:{song.id}:{_content_hash(song)}:{takes}:{quality}",
        payload={"song_id": str(song.id), "batch_id": str(batch_id), "takes": takes, "quality": quality},
    )
    song.status = SongStatus.RENDERING
    await session.commit()
    return job


async def handle_render(session: AsyncSession, job: Job) -> dict:
    song = await session.get(Song, uuid.UUID(job.payload["song_id"]))
    if song is None:
        raise RuntimeError("song vanished")
    storage = get_storage()
    batch_id = uuid.UUID(job.payload["batch_id"])
    out_dir = storage.generation_dir(str(song.id), str(batch_id))
    provider = get_provider()

    async def progress(stage: str) -> None:
        await jobs.report_progress(job.id, stage)

    req = RenderRequest(
        style=song.style, lyrics=song.lyrics or "", duration_s=song.duration_s, bpm=song.bpm, key=song.key,
        vocal_language=song.vocal_language, takes=int(job.payload.get("takes", 2)),
        quality=job.payload.get("quality", "fast"), instrumental=not (song.lyrics or "").strip(), out_dir=out_dir,
    )
    result = await provider.render(req, on_progress=progress)
    await progress("mastering")
    created: list[str] = []
    for i, take in enumerate(result.takes, 1):
        wav, mp3, lufs = await master(Path(take.path))
        gen = Generation(
            song_id=song.id, user_id=song.user_id, job_id=job.id, batch_id=batch_id, take_index=i,
            provider=result.provider, model=take.model, seed=take.seed, params=result.raw.get("request", {}),
            metas=take.metas, duration_s=float(take.metas.get("duration") or song.duration_s),
            wav_path=storage.relative(wav), mp3_path=storage.relative(mp3) if mp3 else None, lufs=lufs,
            render_seconds=result.render_seconds,
        )
        session.add(gen)
        await session.flush()
        created.append(str(gen.id))
    song.status = SongStatus.READY
    await session.commit()
    return {"generation_ids": created, "render_seconds": result.render_seconds, "provider": result.provider}


jobs.register_handler("render", handle_render)

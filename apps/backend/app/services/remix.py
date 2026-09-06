"""Remix job handlers (Phase 4): `analyze` (stems + tempo/key + lyrics) and `remix` (cover + vocal treatment + master).

Modes — the CLI pipeline the user validated, now behind the job runner:
  hybrid       real lead over an AI cover WITH backing vocals (cover of the full song with the transcribed lyrics)
  keep         real lead over a new instrumental bed (cover of the instrumental stem, no lyrics ⇒ instrumental)
  resing       the AI sings the transcribed lyrics in the new style (cover of the full song)
  instrumental cover of the full song with no lyrics
Every mode renders `takes` variations (different seeds). The real vocal is the LEAD: auto-tuned (default ON), clean and
in front; harmonies/doubles/chops are opt-in. For hybrid the AI cover is SEPARATED (Demucs) into music + AI vocals and the
AI vocals are ducked under the lead so they answer in the gaps instead of colliding. The whole mix is stretched to
`bpm_to` AFTER the cover (never before — it drifts).
"""
from __future__ import annotations

import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job, Remix, RemixMode, Stem, Upload, UploadStatus
from app.services import jobs
from app.services.audio.tools import get_audio_tools
from app.services.mastering import master
from app.services.music import CoverRequest, get_provider
from app.services.storage import get_storage

ANALYZE_STAGES = [
    {"key": "queued", "label": "Queued"},
    {"key": "reading", "label": "Reading the file"},
    {"key": "separating", "label": "Separating vocal · drums · bass · other"},
    {"key": "measuring", "label": "Finding tempo, key and loudness"},
    {"key": "lyrics", "label": "Listening for the lyrics"},
]
REMIX_STAGES = [
    {"key": "queued", "label": "Queued"},
    {"key": "rendering", "label": "Performing the new music"},
    {"key": "decoding", "label": "Decoding audio"},
    {"key": "separating", "label": "Separating the AI performance"},
    {"key": "vocals", "label": "Auto-tuning and placing your vocal"},
    {"key": "mastering", "label": "Mastering · loudness to −14 LUFS"},
]

CAPTION_FOR_MODE = {
    RemixMode.HYBRID: ", lush stacked backing vocal harmonies and call-and-response answering the lead vocal",
    RemixMode.KEEP: ", instrumental",
    RemixMode.RESING: "",
    RemixMode.INSTRUMENTAL: ", instrumental, no vocals",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ffmpeg_to_wav(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-ar", "44100", "-ac", "2", str(dst)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"couldn't read that audio file: {r.stderr[-300:]}")


async def enqueue_analyze(session: AsyncSession, upload: Upload) -> Job:
    job = await jobs.enqueue_job(session, kind="analyze", user_id=upload.user_id, stages=ANALYZE_STAGES,
                                 idempotency_key=f"analyze:{upload.id}", payload={"upload_id": str(upload.id)})
    upload.status = UploadStatus.ANALYZING
    await session.commit()
    return job


async def handle_analyze(session: AsyncSession, job: Job) -> dict:
    up = await session.get(Upload, uuid.UUID(job.payload["upload_id"]))
    if up is None:
        raise RuntimeError("upload vanished")
    st, tools = get_storage(), get_audio_tools()
    src = st.absolute(up.source_path)
    out_dir = src.parent / "stems"

    async def progress(k: str) -> None:
        await jobs.report_progress(job.id, k)

    try:
        await progress("separating")
        stems = await tools.separate(src, out_dir)
        await progress("measuring")
        a = await tools.analyze(src)
        await progress("lyrics")
        lyr = await tools.transcribe(Path(stems["vocals"]["path"]), up.vocal_language)
        for old in (await session.execute(select(Stem).where(Stem.upload_id == up.id))).scalars().all():
            await session.delete(old)
        for kind, info in stems.items():
            session.add(Stem(upload_id=up.id, kind=kind, path=st.relative(Path(info["path"])), energy_share=info.get("energy_share")))
        up.duration_s, up.bpm, up.key, up.lufs = a.duration_s, a.bpm, a.key, a.lufs
        if not (up.lyrics or "").strip():  # a take promoted from the Library already carries its exact lyrics
            up.lyrics = lyr.get("text") or ""
        up.lyrics_segments = lyr.get("segments") or []
        up.analysis = {"tools": tools.name, "vocals_energy": stems.get("vocals", {}).get("energy_share"), "language_heard": lyr.get("language")}
        up.status = UploadStatus.ANALYZED
        up.error = None
        await session.commit()
    except Exception as exc:
        up.status = UploadStatus.FAILED
        up.error = str(exc)[:600]
        await session.commit()
        raise
    return {"upload_id": str(up.id), "bpm": up.bpm, "key": up.key, "lyric_lines": len((up.lyrics or "").splitlines())}


async def enqueue_remix(session: AsyncSession, up: Upload, *, mode: RemixMode, style: str, preset_key: str | None, closeness: float,
                        bpm_to: float | None, ai_forward: int, harmony: str, chops: bool, autotune: bool, autotune_strength: float,
                        takes: int, lyrics_override: str | None = None) -> tuple[list[Remix], Job]:
    batch = uuid.uuid4()
    rows = [Remix(user_id=up.user_id, upload_id=up.id, mode=mode, preset_key=preset_key, style=style, closeness=closeness, bpm_to=bpm_to,
                  ai_forward=ai_forward, harmony=harmony, chops=chops, autotune=autotune, autotune_strength=autotune_strength,
                  batch_id=batch, take_index=i + 1, status="queued") for i in range(max(1, min(4, takes)))]
    session.add_all(rows)
    await session.flush()
    job = await jobs.enqueue_job(session, kind="remix", user_id=up.user_id, stages=REMIX_STAGES,
                                 payload={"upload_id": str(up.id), "remix_ids": [str(r.id) for r in rows], "lyrics_override": lyrics_override})
    for r in rows:
        r.job_id = job.id
    await session.commit()
    return rows, job


async def handle_remix(session: AsyncSession, job: Job) -> dict:
    up = await session.get(Upload, uuid.UUID(job.payload["upload_id"]))
    remixes = [await session.get(Remix, uuid.UUID(rid)) for rid in job.payload["remix_ids"]]
    remixes = [r for r in remixes if r is not None]
    if up is None or not remixes:
        raise RuntimeError("remix rows vanished")
    if up.status != UploadStatus.ANALYZED:
        raise RuntimeError("analyze the upload first")
    st, tools, provider = get_storage(), get_audio_tools(), get_provider()
    stems = {s.kind: st.absolute(s.path) for s in (await session.execute(select(Stem).where(Stem.upload_id == up.id))).scalars().all()}
    src = st.absolute(up.source_path)
    lyrics = job.payload.get("lyrics_override") or up.lyrics or ""
    out_dir = src.parent / "remixes" / str(remixes[0].batch_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    async def progress(k: str) -> None:
        await jobs.report_progress(job.id, k)

    for r in remixes:
        r.status = "rendering"
    await session.commit()
    done: list[str] = []
    try:
        for r in remixes:
            mode = r.mode
            cover_src = stems.get("instrumental", src) if mode == RemixMode.KEEP else src
            cover_lyrics = "" if mode in (RemixMode.KEEP, RemixMode.INSTRUMENTAL) else lyrics
            caption = r.style + CAPTION_FOR_MODE[mode]
            res = await provider.cover(CoverRequest(src_path=cover_src, style=caption, lyrics=cover_lyrics, strength=r.closeness,
                                                    bpm=int(round(up.bpm)) if up.bpm else None, vocal_language=up.vocal_language,
                                                    out_dir=out_dir / f"take-{r.take_index}"), on_progress=progress)
            bed = res.takes[0].path
            ai_vocals = None
            if mode == RemixMode.HYBRID and "vocals" in stems:
                await progress("separating")  # split the AI cover so its vocals can sit UNDER the real lead, ducked
                cov = await tools.separate(bed, out_dir / f"take-{r.take_index}" / "cover-stems")
                bed, ai_vocals = Path(cov["instrumental"]["path"]), Path(cov["vocals"]["path"])
            await progress("vocals")
            mixed = out_dir / f"take-{r.take_index}" / "mix.wav"
            cfg = {"vocal": str(stems["vocals"]) if mode in (RemixMode.HYBRID, RemixMode.KEEP) and "vocals" in stems else None,
                   "bed": str(bed), "ai_vocals": str(ai_vocals) if ai_vocals else None, "out": str(mixed),
                   "bpm": float(up.bpm or 120), "key": up.key or "", "harmony": r.harmony, "doubles": False, "chops": r.chops,
                   "ai_level_db": float(-8 + 2 * r.ai_forward), "ai_duck_db": 12.0, "bed_under": 2.0,
                   "bpm_to": float(r.bpm_to or 0), "autotune": r.autotune, "autotune_strength": r.autotune_strength}
            m = await tools.vocal_mix(cfg)
            await progress("mastering")
            wav, mp3, lufs = await master(Path(m["out"]))
            r.wav_path, r.mp3_path = st.relative(wav), (st.relative(mp3) if mp3 else None)
            r.lufs = lufs if lufs is not None else m.get("lufs")
            r.duration_s, r.render_seconds, r.seed = m.get("duration_s"), res.render_seconds, res.takes[0].seed
            r.params = {"caption": caption, "cover": res.raw.get("request", {}), "notes_tuned": m.get("notes_tuned"),
                        "mix": {k: v for k, v in cfg.items() if k not in ("vocal", "bed", "ai_vocals", "out")}}
            r.status = "ready"
            r.error = None
            await session.commit()
            done.append(str(r.id))
    except Exception as exc:
        for r in remixes:
            if r.status != "ready":
                r.status = "failed"
                r.error = str(exc)[:600]
        await session.commit()
        raise
    return {"remix_ids": done, "batch_id": str(remixes[0].batch_id)}


def delete_upload_files(up: Upload) -> None:
    folder = get_storage().root / "uploads" / str(up.id)
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)


jobs.register_handler("analyze", handle_analyze)
jobs.register_handler("remix", handle_remix)

"""The `align` job: get real line timings for ONE rendered audio so the lyrics can follow playback.

Timings are per-audio on purpose — two takes of the same lyric phrase it differently, and a re-sung remix differs again.
Whisper transcribes the file; we keep its segment times but prefer the WORDS we already know (the song's or upload's
lyrics), matching line by line, so a mis-heard word never replaces the real one.

Two ways lines get a time:
  exact   the known line matched a heard segment by text — reliable, used whenever it works.
  approx  text matching failed for most lines, so lines are spread across the heard segments in order. This is the
          normal case for Hindi/Urdu/Punjabi, where our lyrics are ROMANIZED by product rule but Whisper returns native
          script — the two never match as text even though the audio is right. Approximate lines are flagged so the UI
          can say so rather than implying a precision we don't have.
"""
from __future__ import annotations

import uuid
from difflib import SequenceMatcher
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Generation, Job, Remix, Song, Upload
from app.services import jobs
from app.services.audio.tools import get_audio_tools
from app.services.storage import get_storage

ALIGN_STAGES = [
    {"key": "queued", "label": "Queued"},
    {"key": "listening", "label": "Listening for the lines"},
    {"key": "matching", "label": "Matching them to your lyrics"},
]


def _norm(t: str) -> str:
    return "".join(c.lower() for c in t if c.isalnum() or c.isspace()).strip()


def _spread(lines: list[str], heard: list[dict]) -> list[dict]:
    """Fallback: put the known lines on the heard timeline in order, proportionally. Every line is marked `approx`."""
    out: list[dict] = []
    n = len(lines)
    if not n:
        return out
    for i, text in enumerate(lines):
        seg = heard[min(len(heard) - 1, (i * len(heard)) // n)]
        nxt = heard[min(len(heard) - 1, ((i + 1) * len(heard)) // n)]
        out.append({"text": text, "start": round(seg["start"], 2), "end": round(max(seg["end"], nxt["start"]), 2), "approx": True})
    return out


def match_lines(known: str, heard: list[dict]) -> list[dict]:
    """Give each KNOWN lyric line the time of the heard segment it best matches, in order.

    Section tags ([Chorus]) are kept as markers with the time of the line that follows. Lines Whisper never heard get no
    time and simply don't highlight — better than guessing a position that drifts.
    """
    lines = [ln.rstrip() for ln in (known or "").splitlines()]
    if not lines or not heard:
        return [{"text": s["text"], "start": s["start"], "end": s["end"]} for s in heard or []]
    out: list[dict] = []
    hi = 0
    for ln in lines:
        stripped = ln.strip()
        if not stripped:
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            out.append({"text": stripped, "tag": True})
            continue
        best, best_score = None, 0.0
        for j in range(hi, min(hi + 4, len(heard))):  # only look ahead: lyrics and audio run in the same order
            score = SequenceMatcher(None, _norm(stripped), _norm(heard[j]["text"])).ratio()
            if score > best_score:
                best, best_score = j, score
        if best is not None and best_score >= 0.45:
            out.append({"text": stripped, "start": heard[best]["start"], "end": heard[best]["end"]})
            hi = best + 1
        else:
            out.append({"text": stripped})
    # If text matching mostly failed the two sides are probably in different scripts (romanized lyrics vs native-script
    # transcription). Fall back to spreading the lines across the heard timeline, clearly marked approximate.
    sung = [o for o in out if not o.get("tag")]
    if sung and sum(1 for o in sung if "start" in o) / len(sung) < 0.34:
        spread = _spread([o["text"] for o in sung], heard)
        out = []
        si = 0
        for ln in lines:
            stripped = ln.strip()
            if not stripped:
                continue
            if stripped.startswith("[") and stripped.endswith("]"):
                out.append({"text": stripped, "tag": True})
            else:
                out.append(spread[si]); si += 1
    # a tag marker inherits the time of the next timed line, so the section header highlights with its first line
    for i, item in enumerate(out):
        if item.get("tag"):
            nxt = next((o for o in out[i + 1:] if "start" in o), None)
            if nxt:
                item["start"], item["end"] = nxt["start"], nxt["start"]
    return out


async def enqueue_align(session: AsyncSession, *, kind: str, row_id: uuid.UUID, user_id: uuid.UUID) -> Job:
    return await jobs.enqueue_job(session, kind="align", user_id=user_id, stages=ALIGN_STAGES,
                                  idempotency_key=f"align:{kind}:{row_id}", payload={"kind": kind, "id": str(row_id)})


async def handle_align(session: AsyncSession, job: Job) -> dict:
    kind, row_id = job.payload["kind"], uuid.UUID(job.payload["id"])
    st, tools = get_storage(), get_audio_tools()
    if kind == "generation":
        row = await session.get(Generation, row_id)
        if row is None:
            raise RuntimeError("take vanished")
        song = await session.get(Song, row.song_id)
        known, lang, path = (song.lyrics if song else ""), (song.vocal_language if song else "en"), row.wav_path
    else:
        row = await session.get(Remix, row_id)
        if row is None:
            raise RuntimeError("remix vanished")
        up = await session.get(Upload, row.upload_id)
        brief = row.brief or {}
        known, lang = (brief.get("lyrics") or (up.lyrics if up else "")), (up.vocal_language if up else "en")
        path = row.wav_path
    if not path:
        raise RuntimeError("nothing rendered to align")
    await jobs.report_progress(job.id, "listening")
    heard = await tools.transcribe(Path(st.absolute(path)), lang)
    await jobs.report_progress(job.id, "matching")
    row.lyrics_segments = match_lines(known, heard.get("segments") or [])
    await session.commit()
    segs = row.lyrics_segments or []
    return {"kind": kind, "id": str(row_id), "lines": len(segs), "timed": sum(1 for x in segs if "start" in x),
            "approximate": any(x.get("approx") for x in segs)}


jobs.register_handler("align", handle_align)

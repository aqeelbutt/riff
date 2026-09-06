"""Lyrics: POST /lyrics/brief (structured) · POST /lyrics/write (SSE stream) · POST /lyrics/section (rewrite one section)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.core.auth import current_user
from app.models import User
from app.services.ai.lyrics import BriefInput, SongBrief, caption_from_brief, get_lyrics_provider, parse_sections

router = APIRouter(prefix="/lyrics", tags=["lyrics"])


class BriefOut(BaseModel):
    brief: SongBrief
    engine_caption: str


class WriteInput(BaseModel):
    brief: SongBrief
    keywords: str = Field(min_length=1, max_length=500)
    explicit: bool = False


class SectionInput(BaseModel):
    lyrics: str = Field(min_length=1, max_length=8000)
    tag: str = Field(min_length=1, max_length=60)
    instruction: str = Field(default="rewrite it fresh, same meaning, better images", max_length=300)


@router.post("/brief", response_model=BriefOut)
async def make_brief(body: BriefInput, user: User = Depends(current_user)) -> BriefOut:
    try:
        brief = await get_lyrics_provider().brief(body, user_id=user.id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"couldn't write the brief: {exc}") from exc
    return BriefOut(brief=brief, engine_caption=caption_from_brief(brief))


@router.post("/write")
async def write_lyrics(body: WriteInput, user: User = Depends(current_user)) -> EventSourceResponse:
    """Server-sent events: {type:'delta', text} … then {type:'done', lyrics, sections}. Errors arrive as {type:'error'}."""
    provider = get_lyrics_provider()

    async def gen():
        buf: list[str] = []
        try:
            async for chunk in provider.write(body.brief, body.keywords, body.explicit, user_id=user.id):
                buf.append(chunk)
                yield {"event": "message", "data": json.dumps({"type": "delta", "text": chunk})}
            text = "".join(buf)
            yield {"event": "message", "data": json.dumps({"type": "done", "lyrics": text, "sections": parse_sections(text)})}
        except Exception as exc:  # noqa: BLE001
            yield {"event": "message", "data": json.dumps({"type": "error", "message": str(exc)[:300]})}

    return EventSourceResponse(gen())


@router.post("/section")
async def rewrite_section(body: SectionInput, user: User = Depends(current_user)) -> dict:
    if not any(s["tag"].lower() == body.tag.lower() for s in parse_sections(body.lyrics)):
        raise HTTPException(422, f"no section tagged [{body.tag}] in the lyrics")
    try:
        text = await get_lyrics_provider().rewrite_section(body.lyrics, body.tag, body.instruction, user_id=user.id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"couldn't rewrite the section: {exc}") from exc
    return {"tag": body.tag, "lines": [ln for ln in text.splitlines() if ln.strip()]}

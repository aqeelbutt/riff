"""Claude writes the song: brief (structured) → lyrics (streamed) → section rewrite.

Provider seam like music/: `ClaudeLyrics` (real) vs `FakeLyrics` (tests / no key). Pure helpers (`caption_from_brief`,
`parse_sections`, prompt builders) are unit-tested without the SDK.
"""
from __future__ import annotations

import json
import re
import uuid
from collections.abc import AsyncIterator
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.services.ai import telemetry

ROMANIZED = {"hi", "ur", "pa", "bn"}  # the user's rule: Roman script for these (it sounds better on the engine)

SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")


class SongBrief(BaseModel):
    """Structured output schema — every field required, no extras (structured-output contract)."""

    model_config = ConfigDict(extra="forbid")
    titles: list[str] = Field(description="three short title options, best first")
    genre: str = Field(description="one line, e.g. 'Modern pop · synth bass, bright guitars'")
    style_caption: str = Field(description="the engine caption: genre, instruments, drums, vocal, mood, production; no artist names")
    bpm: int = Field(description="tempo in BPM")
    key: str = Field(description="musical key, e.g. 'D major'")
    mood: str = Field(description="two or three mood words joined with ' · '")
    vocal: Literal["female", "male", "duet", "instrumental"]
    vocal_language: str = Field(description="ISO code: en, hi, ur, pa, bn, es, fr, ar")
    structure: list[str] = Field(description="section tags in order, e.g. ['Intro','Verse 1','Pre-Chorus','Chorus','Verse 2','Chorus','Bridge','Chorus','Outro']")
    duration_s: int = Field(description="target length in seconds")
    hook_idea: str = Field(description="the chorus's central image or line, one sentence")


class Reimagined(BaseModel):
    """Structured output for REIMAGINE: understand an existing song (its transcribed lyrics + measured key/tempo) and write
    the arrangement brief for a fresh, melodic, impactful performance of the SAME words."""

    model_config = ConfigDict(extra="forbid")
    title: str = Field(description="a title for this version")
    meaning: str = Field(description="one or two sentences: what the song is about and its emotional arc")
    style_caption: str = Field(description="the engine caption for the new arrangement: genre, concrete instruments, dynamics/arc, vocal delivery, production; no artist names")
    bpm: int = Field(description="tempo for the new arrangement")
    key: str = Field(description="musical key — keep the original unless there is a strong reason")
    vocal: Literal["female", "male", "duet"]
    lyrics: str = Field(description="the SAME lyrics, cleaned and organized into sections with tags on their own lines ([Intro] [Verse 1] [Pre-Chorus] [Chorus] [Verse 2] [Bridge] [Outro]); repeated lines become the chorus; feel hints allowed like [Chorus - soaring]; in ROMAN script for hi/ur/pa/bn")
    structure: list[str] = Field(description="the section tags in order")
    arc: str = Field(description="how the dynamics move: where it is intimate, where it lifts, where it peaks")


class ReimagineInput(BaseModel):
    lyrics: str = Field(min_length=3, max_length=8000)
    key: str | None = None
    bpm: float | None = None
    vocal_language: str = "en"
    direction: str = Field(default="emotional ballad", max_length=200, description="e.g. emotional ballad, cinematic anthem, acoustic, sufi-pop, pop anthem")
    direction_caption: str | None = Field(default=None, max_length=600)
    vocal: Literal["female", "male", "duet"] = "male"
    duration_s: int = Field(default=180, ge=60, le=600)


SYSTEM_REIMAGINE = """You are a producer and arranger reinterpreting an existing song from its lyrics. First understand it: what the
words mean, the emotional arc, which lines repeat (that is the chorus). Then design a NEW performance of the SAME words in the
requested direction that is melodic, dynamic and impactful: clear verses that stay intimate, a chorus that lifts, a bridge or
final chorus that peaks. Keep the original key unless there is a strong musical reason. The style_caption is read by a music
engine: name concrete instruments, the drum feel (or no drums), the dynamic arc, the vocal delivery, the production; never a real
artist's name. Lyrics: keep the words (fix obvious transcription slips), do NOT add new verses, organize into tagged sections,
and if the language is Hindi/Urdu/Punjabi/Bengali write them in ROMAN script exactly as they are sung. Answer only with the JSON."""


def reimagine_prompt(inp: ReimagineInput) -> str:
    return (f"Direction: {inp.direction}" + (f"\nDirection caption to build on: {inp.direction_caption}" if inp.direction_caption else "")
            + f"\nOriginal key: {inp.key or 'unknown'}\nOriginal tempo: {inp.bpm or 'unknown'} BPM\nLanguage: {inp.vocal_language}\nVocal: {inp.vocal}"
            f"\nTarget length: {inp.duration_s} seconds\n\nLyrics as transcribed (may contain slips):\n{inp.lyrics}")


class BriefInput(BaseModel):
    keywords: str = Field(min_length=2, max_length=500)
    style: str = Field(default="Pop", max_length=200, description="preset label or free text")
    style_caption: str | None = Field(default=None, max_length=600, description="preset caption if a preset was picked")
    moods: list[str] = Field(default_factory=list)
    vocal: Literal["female", "male", "duet", "instrumental"] = "female"
    vocal_language: str = Field(default="en", max_length=8)
    duration_s: int = Field(default=150, ge=30, le=600)
    explicit: bool = False


SYSTEM_BRIEF = """You are the producer in a songwriting session. Turn a few words from the artist into a concrete song brief.
Rules: pick a tempo and key that fit the style; the style_caption is what a music engine will read — name concrete instruments,
drums, the vocal, mood and production, never a real artist's name (describe traits instead). Titles: three, short, memorable.
Structure: 8–11 sections using only these tags: Intro, Verse 1, Verse 2, Verse 3, Pre-Chorus, Chorus, Bridge, Outro, Hook.
Answer only with the JSON object."""

SYSTEM_LYRICS = """You are a hit songwriter. Write complete, singable lyrics for the brief you are given.
Format: each section starts with its tag on its own line in square brackets, exactly as listed in the brief's structure, e.g. [Verse 1].
You may add a short feel to a tag: [Chorus - anthemic], [Bridge - soft, building]. Lines are short (4–10 words), concrete images,
a chorus that repeats verbatim, rhyme that feels natural, no clichés, no explanations, no title line, no blank tags.
If the language is not English, write the ENTIRE lyric in that language using ROMAN script (Latin letters, as people type it),
never native script. Keep it clean unless the brief says explicit. Output the lyrics only."""

SYSTEM_SECTION = """You are a hit songwriter revising one section of an existing lyric. Keep the song's voice, tense, rhyme feel,
language and script (Roman script for non-English). Return ONLY the new lines for that section — no tag, no commentary."""


def caption_from_brief(b: SongBrief) -> str:
    """The engine caption: the brief's caption plus the vocal and language, deduplicated."""
    parts = [b.style_caption.strip().rstrip(",")]
    voc = {"female": "female lead vocal", "male": "male lead vocal", "duet": "male and female duet vocals", "instrumental": "instrumental, no vocals"}[b.vocal]
    if voc.split()[0] not in b.style_caption.lower():
        parts.append(voc)
    return ", ".join(p for p in parts if p)


def parse_sections(text: str) -> list[dict]:
    """'[Verse 1]\\nline\\nline\\n\\n[Chorus]…' → [{tag, lines}] (tag without brackets; feel suffix kept)."""
    out: list[dict] = []
    cur: dict | None = None
    for raw in (text or "").splitlines():
        m = SECTION_RE.match(raw)
        if m:
            cur = {"tag": m.group(1).strip(), "lines": []}
            out.append(cur)
        elif raw.strip():
            if cur is None:
                cur = {"tag": "Verse 1", "lines": []}
                out.append(cur)
            cur["lines"].append(raw.rstrip())
    return out


def serialize_sections(sections: list[dict]) -> str:
    return "\n\n".join(f"[{s['tag']}]\n" + "\n".join(s["lines"]) for s in sections if s.get("tag")).strip() + "\n"


def brief_prompt(inp: BriefInput) -> str:
    moods = ", ".join(inp.moods) if inp.moods else "your call"
    return (f"Artist's words: {inp.keywords}\nStyle: {inp.style}" + (f"\nStyle caption to build on: {inp.style_caption}" if inp.style_caption else "")
            + f"\nMood: {moods}\nVocal: {inp.vocal}\nLanguage: {inp.vocal_language}\nTarget length: {inp.duration_s} seconds\nExplicit allowed: {inp.explicit}")


def lyrics_prompt(brief: SongBrief, keywords: str, explicit: bool = False) -> str:
    return (f"Brief:\n{json.dumps(brief.model_dump(), ensure_ascii=False, indent=1)}\n\nThe artist's words: {keywords}\n"
            f"Explicit allowed: {explicit}\nWrite the full lyric now, section by section in the brief's structure.")


def section_prompt(lyrics: str, tag: str, instruction: str) -> str:
    return f"Full lyric:\n{lyrics}\n\nRewrite the section tagged [{tag}]. Instruction: {instruction}"


class FakeLyrics:
    """Deterministic, instant. Used by tests and when no API key is configured."""

    name = "fake"

    async def brief(self, inp: BriefInput, user_id: uuid.UUID | None = None) -> SongBrief:
        return SongBrief(titles=["Run With Me", "Gold in the Dark", "Long Way Home"], genre=f"{inp.style} · fake",
                         style_caption=inp.style_caption or f"{inp.style.lower()}, driving drums, bright guitars", bpm=118, key="D major",
                         mood=" · ".join(inp.moods[:2]) or "euphoric · nostalgic", vocal=inp.vocal, vocal_language=inp.vocal_language,
                         structure=["Intro", "Verse 1", "Chorus", "Verse 2", "Chorus", "Bridge", "Chorus", "Outro"],
                         duration_s=inp.duration_s, hook_idea="running through the city till morning")

    async def write(self, brief: SongBrief, keywords: str, explicit: bool = False, user_id: uuid.UUID | None = None) -> AsyncIterator[str]:
        text = "".join(f"[{t}]\n" + ("La la la " + keywords[:20] + "\nWe run until the morning breaks\n") + "\n" for t in brief.structure)
        for i in range(0, len(text), 24):
            yield text[i:i + 24]

    async def rewrite_section(self, lyrics: str, tag: str, instruction: str, user_id: uuid.UUID | None = None) -> str:
        return f"Rewritten {tag} ({instruction})\nSecond line of the rewrite"

    async def reimagine(self, inp: ReimagineInput, user_id: uuid.UUID | None = None) -> Reimagined:
        lines = [ln for ln in inp.lyrics.splitlines() if ln.strip()]
        return Reimagined(title="Reimagined", meaning="a song about trust and love overcoming hardship", style_caption=f"{inp.direction}, piano, strings, building dynamics",
                          bpm=int(inp.bpm or 84), key=inp.key or "C major", vocal=inp.vocal,
                          lyrics="[Verse 1]\n" + "\n".join(lines[:2]) + "\n\n[Chorus - soaring]\n" + "\n".join(lines[2:4] or lines[:1]),
                          structure=["Verse 1", "Chorus"], arc="intimate verse, lifting chorus")


class ClaudeLyrics:
    name = "claude"

    def __init__(self) -> None:
        import anthropic

        s = get_settings()
        self.client = anthropic.AsyncAnthropic(api_key=s.anthropic_api_key or None)
        self.model = s.claude_model
        self.effort = s.claude_effort

    def _system(self, text: str) -> list[dict]:
        return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]  # stable prefix → cached

    async def brief(self, inp: BriefInput, user_id: uuid.UUID | None = None) -> SongBrief:
        async with telemetry.timed("lyrics_brief", self.model, user_id) as t:
            r = await self.client.messages.create(
                model=self.model, max_tokens=4000, system=self._system(SYSTEM_BRIEF),
                output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": SongBrief.model_json_schema()}},
                messages=[{"role": "user", "content": brief_prompt(inp)}],
            )
            t["usage"] = r.usage
            if r.stop_reason == "refusal":
                raise RuntimeError("the model declined this brief")
            text = next(b.text for b in r.content if b.type == "text")
            brief = SongBrief.model_validate_json(text)
        if brief.vocal_language in ROMANIZED:
            brief.vocal_language = brief.vocal_language.lower()
        return brief

    async def write(self, brief: SongBrief, keywords: str, explicit: bool = False, user_id: uuid.UUID | None = None) -> AsyncIterator[str]:
        async with telemetry.timed("lyrics_write", self.model, user_id) as t:
            async with self.client.messages.stream(
                model=self.model, max_tokens=8000, system=self._system(SYSTEM_LYRICS), output_config={"effort": self.effort},
                messages=[{"role": "user", "content": lyrics_prompt(brief, keywords, explicit)}],
            ) as stream:
                async for chunk in stream.text_stream:
                    yield chunk
                final = await stream.get_final_message()
                t["usage"] = final.usage
                if final.stop_reason == "refusal":
                    raise RuntimeError("the model declined these lyrics")

    async def reimagine(self, inp: ReimagineInput, user_id: uuid.UUID | None = None) -> Reimagined:
        async with telemetry.timed("reimagine_brief", self.model, user_id) as t:
            r = await self.client.messages.create(
                model=self.model, max_tokens=6000, system=self._system(SYSTEM_REIMAGINE),
                output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": Reimagined.model_json_schema()}},
                messages=[{"role": "user", "content": reimagine_prompt(inp)}],
            )
            t["usage"] = r.usage
            if r.stop_reason == "refusal":
                raise RuntimeError("the model declined this reinterpretation")
            text = next(b.text for b in r.content if b.type == "text")
            return Reimagined.model_validate_json(text)

    async def rewrite_section(self, lyrics: str, tag: str, instruction: str, user_id: uuid.UUID | None = None) -> str:
        async with telemetry.timed("lyrics_section", self.model, user_id) as t:
            r = await self.client.messages.create(
                model=self.model, max_tokens=2000, system=self._system(SYSTEM_SECTION), output_config={"effort": self.effort},
                messages=[{"role": "user", "content": section_prompt(lyrics, tag, instruction)}],
            )
            t["usage"] = r.usage
            if r.stop_reason == "refusal":
                raise RuntimeError("the model declined this rewrite")
            text = "".join(b.text for b in r.content if b.type == "text").strip()
        # strip a tag line if the model echoed one
        lines = [ln for ln in text.splitlines() if not SECTION_RE.match(ln)]
        return "\n".join(lines).strip()


_override = None


def set_lyrics_provider(p) -> None:
    global _override
    _override = p


def get_lyrics_provider():
    if _override is not None:
        return _override
    s = get_settings()
    if s.lyrics_provider == "fake" or (s.lyrics_provider == "auto" and not s.anthropic_api_key):
        return FakeLyrics()
    return ClaudeLyrics()

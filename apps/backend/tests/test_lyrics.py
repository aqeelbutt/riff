"""Lyrics: pure helpers, the structured-output schema contract, the three endpoints (fake provider), telemetry rows."""
from __future__ import annotations

import json

from sqlalchemy import select

from app.services.ai.lyrics import (BriefInput, SongBrief, brief_prompt, caption_from_brief, parse_sections, serialize_sections)
from app.services.ai.telemetry import AiCallTelemetry, cost_usd

LYR = "[Intro]\nOoh\n\n[Verse 1]\nStreetlights flicker\nWindows down\n\n[Chorus - anthemic]\nRun with me\n"


def test_parse_and_serialize_sections_round_trip():
    secs = parse_sections(LYR)
    assert [s["tag"] for s in secs] == ["Intro", "Verse 1", "Chorus - anthemic"]
    assert secs[1]["lines"] == ["Streetlights flicker", "Windows down"]
    assert parse_sections(serialize_sections(secs)) == secs


def test_parse_untagged_text_becomes_verse_1():
    assert parse_sections("just a line\nanother")[0] == {"tag": "Verse 1", "lines": ["just a line", "another"]}


def test_brief_schema_is_strict_structured_output():
    schema = SongBrief.model_json_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])  # every field required — the structured-output contract


def test_caption_adds_vocal_once():
    b = SongBrief(titles=["a", "b", "c"], genre="g", style_caption="deep house, warm pads, female lead vocal", bpm=124, key="C minor", mood="m",
                  vocal="female", vocal_language="en", structure=["Verse 1", "Chorus"], duration_s=120, hook_idea="h")
    assert caption_from_brief(b) == "deep house, warm pads, female lead vocal"
    b.style_caption = "deep house, warm pads"
    assert caption_from_brief(b).endswith("female lead vocal")
    b.vocal = "instrumental"
    assert "instrumental, no vocals" in caption_from_brief(b)


def test_brief_prompt_carries_every_input():
    p = brief_prompt(BriefInput(keywords="late night drive", style="Jazz-Rap", style_caption="rhodes", moods=["Chill"], vocal="male",
                                vocal_language="ur", duration_s=90))
    for needle in ("late night drive", "Jazz-Rap", "rhodes", "Chill", "male", "ur", "90"):
        assert needle in p


def test_cost_table():
    assert cost_usd("claude-opus-5", 1_000_000, 0) == 5.0
    assert cost_usd("claude-opus-5", 0, 1_000_000) == 25.0
    assert cost_usd("claude-opus-5", 1_000_000, 0, cache_read_tokens=1_000_000) == 0.5


async def test_brief_endpoint(client):
    r = await client.post("/lyrics/brief", json={"keywords": "late night drive, neon", "style": "Pop", "moods": ["Euphoric"], "vocal_language": "en"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["brief"]["titles"][0] == "Run With Me" and body["brief"]["bpm"] == 118
    assert "female lead vocal" in body["engine_caption"]


async def test_write_streams_sse_then_done_with_sections(client, fake_lyrics):
    brief = (await client.post("/lyrics/brief", json={"keywords": "x y", "style": "Pop"})).json()["brief"]
    async with client.stream("POST", "/lyrics/write", json={"brief": brief, "keywords": "x y"}) as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        events = []
        async for line in r.aiter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))
    assert events[0]["type"] == "delta" and events[-1]["type"] == "done"
    assert "".join(e["text"] for e in events if e["type"] == "delta") == events[-1]["lyrics"]
    assert [s["tag"] for s in events[-1]["sections"]] == brief["structure"]


async def test_section_rewrite_and_unknown_tag(client):
    r = await client.post("/lyrics/section", json={"lyrics": LYR, "tag": "Verse 1", "instruction": "shorter"})
    assert r.status_code == 200 and r.json()["tag"] == "Verse 1" and len(r.json()["lines"]) == 2
    r = await client.post("/lyrics/section", json={"lyrics": LYR, "tag": "Verse 9"})
    assert r.status_code == 422


async def test_telemetry_row_written_on_success_and_failure(client, session, fake_lyrics, monkeypatch):
    from app.services.ai import telemetry

    class Usage:
        input_tokens, output_tokens, cache_read_input_tokens = 1200, 300, 1000

    async def ok_brief(inp, user_id=None):
        async with telemetry.timed("lyrics_brief", "claude-opus-5", user_id) as t:
            t["usage"] = Usage()
            return await FakeLyricsBrief(inp)

    async def FakeLyricsBrief(inp):
        return await fake_lyrics.__class__().brief(inp)

    async def bad_brief(inp, user_id=None):
        async with telemetry.timed("lyrics_brief", "claude-opus-5", user_id):
            raise RuntimeError("boom")

    monkeypatch.setattr(fake_lyrics, "brief", ok_brief)
    assert (await client.post("/lyrics/brief", json={"keywords": "a b"})).status_code == 200
    monkeypatch.setattr(fake_lyrics, "brief", bad_brief)
    r = await client.post("/lyrics/brief", json={"keywords": "a b"})
    assert r.status_code == 502 and "boom" in r.json()["detail"]
    rows = (await session.execute(select(AiCallTelemetry).order_by(AiCallTelemetry.created_at))).scalars().all()
    assert [r.ok for r in rows] == [True, False]
    assert rows[0].input_tokens == 1200 and rows[0].cache_read_tokens == 1000 and rows[0].cost_usd == cost_usd("claude-opus-5", 1200, 300, 1000)
    assert "boom" in rows[1].error and rows[1].feature == "lyrics_brief"

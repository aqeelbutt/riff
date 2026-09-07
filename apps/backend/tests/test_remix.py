"""Remix (Phase 4): upload → analyze job → stems/lyrics → remix job per mode with variations + auto-tune → outputs; from-generation; delete."""
from __future__ import annotations

import io
import math
import struct
import wave

from app.services import jobs
from app.services.storage import get_storage


def _wav_bytes(seconds=1.0, sr=8000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(3000 * math.sin(2 * math.pi * 330 * n / sr))) for n in range(int(sr * seconds))))
    return buf.getvalue()


async def _analyzed(client, lang="ur"):
    r = await client.post("/uploads", files={"file": ("Aqeel Test 1.wav", _wav_bytes(), "audio/wav")}, data={"rights": "true", "vocal_language": lang})
    assert r.status_code == 202, r.text
    up, job = r.json()["upload"], r.json()["job"]
    assert up["status"] == "analyzing" and up["title"] == "Aqeel Test 1"
    assert [s["key"] for s in job["progress"]["stages"]] == ["queued", "reading", "separating", "measuring", "lyrics"]
    assert await jobs.run_once() is True
    j = (await client.get(f"/jobs/{job['id']}")).json()
    assert j["status"] == "done", j
    return (await client.get(f"/uploads/{up['id']}")).json()


async def test_upload_requires_rights_and_audio(client):
    r = await client.post("/uploads", files={"file": ("x.wav", _wav_bytes(), "audio/wav")}, data={"rights": "false"})
    assert r.status_code == 422
    r = await client.post("/uploads", files={"file": ("notes.txt", b"hello", "text/plain")}, data={"rights": "true"})
    assert r.status_code == 415


async def test_analyze_fills_stems_facts_and_lyrics(client):
    up = await _analyzed(client)
    assert up["status"] == "analyzed" and up["bpm"] == 126.0 and up["key"] == "G major" and up["duration_s"] == 3.0
    assert {s["kind"] for s in up["stems"]} == {"vocals", "drums", "bass", "other", "instrumental"}
    assert up["lyrics"].startswith("Bolne se sach") and len(up["lyrics_segments"]) == 2
    assert up["analysis"]["tools"] == "fake" and up["analysis"]["vocals_energy"] == 0.25
    r = await client.get(f"/uploads/{up['id']}/stems/vocals")
    assert r.status_code == 200 and r.headers["content-type"].startswith("audio/wav")
    assert (await client.get(f"/uploads/{up['id']}/audio")).status_code == 200
    assert (await client.get(f"/uploads/{up['id']}/stems/nope")).status_code == 404


async def test_lyrics_can_be_corrected_before_remix(client):
    up = await _analyzed(client)
    r = await client.patch(f"/uploads/{up['id']}", json={"lyrics": "Fixed line one\nFixed line two", "vocal_language": "hi"})
    assert r.status_code == 200 and r.json()["lyrics"] == "Fixed line one\nFixed line two" and r.json()["vocal_language"] == "hi"


async def test_remix_hybrid_default_two_variations_with_autotune(client, fake_provider, fake_tools, monkeypatch):
    up = await _analyzed(client)
    seen = []
    real_mix = fake_tools.vocal_mix

    async def spy(cfg):
        seen.append(cfg)
        return await real_mix(cfg)

    monkeypatch.setattr(fake_tools, "vocal_mix", spy)
    r = await client.post(f"/uploads/{up['id']}/remix", json={"preset_key": "chillhouse", "moods": ["Emotional", "Chill"]})
    assert r.status_code == 202, r.text
    rem, job = r.json()["remixes"], r.json()["job"]
    assert len(rem) == 2 and [x["take_index"] for x in rem] == [1, 2] and rem[0]["batch_id"] == rem[1]["batch_id"]
    assert rem[0]["mode"] == "hybrid" and rem[0]["autotune"] is True and rem[0]["autotune_strength"] == 0.85
    assert rem[0]["closeness"] == 0.5  # the preset's default closeness
    assert "chill downtempo deep house" in rem[0]["style"] and rem[0]["style"].endswith("emotional, chill")
    assert [s["key"] for s in job["progress"]["stages"]] == ["queued", "rendering", "decoding", "separating", "vocals", "mastering"]
    assert await jobs.run_once() is True
    assert (await client.get(f"/jobs/{job['id']}")).json()["status"] == "done"
    # the cover carried the transcribed lyrics + language + native bpm; the caption asked for backing vocals
    c = fake_provider.last_cover
    assert c.lyrics.startswith("Bolne se sach") and c.vocal_language == "ur" and c.bpm == 126 and "backing vocal" in c.style
    # the vocal mix got the REAL vocal stem, the key for auto-tune, and the AI-forward → bed_under mapping
    assert len(seen) == 2 and seen[0]["vocal"].endswith("vocals.wav") and seen[0]["key"] == "G major"
    assert seen[0]["autotune"] is True and seen[0]["autotune_strength"] == 0.85 and seen[0]["ai_level_db"] == -6.0 and seen[0]["doubles"] is False
    assert seen[0]["ai_vocals"] and seen[0]["ai_vocals"].endswith("vocals.wav") and "cover-stems" in seen[0]["ai_vocals"]  # hybrid: the AI cover was separated
    out = (await client.get(f"/uploads/{up['id']}")).json()["remixes"]
    assert all(x["status"] == "ready" and x["mp3_url"] is None and x["audio_url"] for x in out)  # mastering off in tests → wav only
    assert (await client.get(out[0]["audio_url"])).status_code == 200
    lst = (await client.get("/remixes")).json()
    assert len(lst) == 2


async def test_remix_modes_route_the_right_source_and_lyrics(client, fake_provider, fake_tools, monkeypatch):
    up = await _analyzed(client)
    seen = []
    real_mix = fake_tools.vocal_mix

    async def spy(cfg):
        seen.append(cfg)
        return await real_mix(cfg)

    monkeypatch.setattr(fake_tools, "vocal_mix", spy)
    for mode, expect_src, expect_lyrics, expect_vocal in (("keep", "instrumental.wav", "", True), ("resing", "source.wav", "Bolne", False), ("instrumental", "source.wav", "", False)):
        seen.clear()
        r = await client.post(f"/uploads/{up['id']}/remix", json={"style": "deep house", "mode": mode, "takes": 1, "autotune": False, "ai_forward": 4, "bpm_to": 118})
        assert r.status_code == 202, r.text
        await jobs.run_once()
        c = fake_provider.last_cover
        assert c.src_path.name == expect_src, mode
        assert c.lyrics.startswith(expect_lyrics) if expect_lyrics else c.lyrics == "", mode
        assert (seen[0]["vocal"] is not None) is expect_vocal, mode
        assert seen[0]["autotune"] is False and seen[0]["ai_level_db"] == 0.0 and seen[0]["bpm_to"] == 118.0 and seen[0]["ai_vocals"] is None
    r = await client.post(f"/uploads/{up['id']}/remix", json={"preset_key": "nope"})
    assert r.status_code == 422
    r = await client.post(f"/uploads/{up['id']}/remix", json={})
    assert r.status_code == 422


async def test_remix_engine_failure_marks_rows_failed_then_retry_succeeds(client, fake_provider):
    up = await _analyzed(client)
    r = await client.post(f"/uploads/{up['id']}/remix", json={"preset_key": "deephouse", "takes": 1})
    job = r.json()["job"]
    fake_provider.fail_next = 1
    await jobs.run_once()
    j = (await client.get(f"/jobs/{job['id']}")).json()
    assert j["status"] == "queued" and j["attempts"] == 1
    assert (await client.get(f"/remixes/{r.json()['remixes'][0]['id']}")).json()["status"] == "failed"
    await jobs.run_once()
    assert (await client.get(f"/jobs/{job['id']}")).json()["status"] == "done"
    assert (await client.get(f"/remixes/{r.json()['remixes'][0]['id']}")).json()["status"] == "ready"


async def test_remix_before_analysis_is_409(client):
    r = await client.post("/uploads", files={"file": ("s.wav", _wav_bytes(), "audio/wav")}, data={"rights": "true"})
    up = r.json()["upload"]
    assert (await client.post(f"/uploads/{up['id']}/remix", json={"preset_key": "deephouse"})).status_code == 409


async def test_remix_from_your_own_take_keeps_known_lyrics(client):
    song = (await client.post("/songs", json={"title": "Run With Me", "style": "pop", "lyrics": "[Verse]\nneon city", "bpm": 118, "duration_s": 30})).json()
    await client.post(f"/songs/{song['id']}/generate", json={"takes": 1})
    await jobs.run_once()
    gen = (await client.get(f"/songs/{song['id']}")).json()["generations"][0]
    r = await client.post(f"/uploads/from-generation/{gen['id']}")
    assert r.status_code == 202, r.text
    up = r.json()["upload"]
    assert up["title"] == "Run With Me" and up["from_generation_id"] == gen["id"] and up["lyrics"] == "[Verse]\nneon city"
    await jobs.run_once()
    after = (await client.get(f"/uploads/{up['id']}")).json()
    assert after["status"] == "analyzed" and after["lyrics"] == "[Verse]\nneon city"  # Whisper must not overwrite known words


async def test_favorite_and_delete_cleanup(client):
    up = await _analyzed(client)
    r = await client.post(f"/uploads/{up['id']}/remix", json={"preset_key": "deephouse", "takes": 1})
    await jobs.run_once()
    rid = r.json()["remixes"][0]["id"]
    assert (await client.post(f"/remixes/{rid}/favorite")).json()["is_favorite"] is True
    folder = get_storage().root / "uploads" / up["id"]
    assert folder.exists()
    assert (await client.delete(f"/remixes/{rid}")).status_code == 204
    assert (await client.get(f"/remixes/{rid}")).status_code == 404
    assert (await client.delete(f"/uploads/{up['id']}")).status_code == 204
    assert not folder.exists()
    assert (await client.get(f"/uploads/{up['id']}")).status_code == 404


async def test_reimagine_reads_the_song_then_performs_it(client, fake_provider, fake_lyrics, monkeypatch):
    """Reimagine: Claude gets the transcribed lyrics + measured key/tempo; the engine RENDERS the arrangement (no cover)."""
    up = await _analyzed(client)
    seen = {}
    real = fake_lyrics.reimagine

    async def spy(inp, user_id=None):
        seen["inp"] = inp
        return await real(inp, user_id)

    monkeypatch.setattr(fake_lyrics, "reimagine", spy)
    r = await client.post(f"/uploads/{up['id']}/remix", json={"mode": "reimagine", "preset_key": "ballad", "takes": 2})
    assert r.status_code == 202, r.text
    rem, job = r.json()["remixes"], r.json()["job"]
    assert rem[0]["mode"] == "reimagine" and rem[0]["direction"] == "Emotional ballad"
    assert [s["key"] for s in job["progress"]["stages"]] == ["queued", "understanding", "rendering", "decoding", "mastering"]
    assert await jobs.run_once() is True
    assert (await client.get(f"/jobs/{job['id']}")).json()["status"] == "done"
    # Claude saw the song's own words, key and tempo
    assert seen["inp"].lyrics.startswith("Bolne se sach") and seen["inp"].key == "G major" and seen["inp"].bpm == 126.0
    assert seen["inp"].vocal_language == "ur" and "emotional pop ballad" in seen["inp"].direction_caption
    out = (await client.get(f"/uploads/{up['id']}")).json()["remixes"]
    assert all(x["status"] == "ready" for x in out) and len(out) == 2
    assert out[0]["brief"]["meaning"] and out[0]["brief"]["arc"]  # the reading is stored for the UI
    # it PERFORMED the arrangement (render) rather than pushing the recording through a cover
    assert fake_provider.last_cover is None
    rq = fake_provider.last_render
    assert rq.style == out[0]["brief"]["style_caption"] and rq.lyrics == out[0]["brief"]["lyrics"]
    assert rq.bpm == out[0]["brief"]["bpm"] and rq.instrumental is False and rq.vocal_language == "ur"


async def test_reimagine_keep_renders_instrumental_at_the_original_tempo_and_places_your_vocal(client, fake_tools, fake_lyrics, monkeypatch):
    up = await _analyzed(client)
    mixes, briefs = [], {}
    real_mix, real_re = fake_tools.vocal_mix, fake_lyrics.reimagine

    async def spy_mix(cfg):
        mixes.append(cfg)
        return await real_mix(cfg)

    async def spy_re(inp, user_id=None):
        briefs["inp"] = inp
        return await real_re(inp, user_id)

    monkeypatch.setattr(fake_tools, "vocal_mix", spy_mix)
    monkeypatch.setattr(fake_lyrics, "reimagine", spy_re)
    r = await client.post(f"/uploads/{up['id']}/remix", json={"mode": "reimagine_keep", "preset_key": "acoustic", "takes": 1})
    assert r.status_code == 202
    job = r.json()["job"]
    assert [s["key"] for s in job["progress"]["stages"]] == ["queued", "understanding", "rendering", "decoding", "vocals", "mastering"]
    await jobs.run_once()
    assert (await client.get(f"/jobs/{job['id']}")).json()["status"] == "done"
    assert "must line up" in briefs["inp"].direction  # the arrangement is told to keep tempo + line order
    assert len(mixes) == 1 and mixes[0]["vocal"].endswith("vocals.wav") and mixes[0]["ai_vocals"] is None
    assert mixes[0]["autotune"] is True and mixes[0]["bpm_to"] == 0.0  # no stretch: the bed was rendered at the song's tempo
    out = (await client.get(f"/uploads/{up['id']}")).json()["remixes"][0]
    assert out["status"] == "ready" and out["params"]["instrumental"] is True
    assert out["params"]["bpm"] == 126  # the ORIGINAL tempo, so the real vocal lines up


async def test_reimagine_needs_lyrics_and_rejects_a_remix_preset(client):
    r = await client.post("/uploads", files={"file": ("q.wav", _wav_bytes(), "audio/wav")}, data={"rights": "true"})
    up = r.json()["upload"]
    await jobs.run_once()
    await client.patch(f"/uploads/{up['id']}", json={"lyrics": ""})
    assert (await client.post(f"/uploads/{up['id']}/remix", json={"mode": "reimagine", "preset_key": "ballad"})).status_code == 409
    await client.patch(f"/uploads/{up['id']}", json={"lyrics": "some words"})
    assert (await client.post(f"/uploads/{up['id']}/remix", json={"mode": "reimagine", "preset_key": "deephouse"})).status_code == 422


# --- preset tempo: the two surfaces must agree -----------------------------------------------------
# The web flow defaults to matching a preset's tempo (deep house IS ~124). An API caller that just named
# the preset used to get the source tempo, so "remix into deep house" meant different things depending on
# which surface asked — a real render came back at 105.5 BPM when 124 was intended.

async def test_naming_a_preset_adopts_its_tempo(client):
    up = await _analyzed(client)
    r = await client.post(f"/uploads/{up['id']}/remix",
                          json={"mode": "hybrid", "preset_key": "deephouse", "takes": 1})
    assert r.status_code == 202
    assert r.json()["remixes"][0]["bpm_to"] == 124


async def test_an_explicit_null_still_keeps_the_source_tempo(client):
    """Unset means 'match the preset'; explicitly asking for no change must still mean no change."""
    up = await _analyzed(client)
    r = await client.post(f"/uploads/{up['id']}/remix",
                          json={"mode": "hybrid", "preset_key": "deephouse", "bpm_to": None, "takes": 1})
    assert r.status_code == 202
    assert r.json()["remixes"][0]["bpm_to"] is None


async def test_an_explicit_tempo_wins_over_the_preset(client):
    up = await _analyzed(client)
    r = await client.post(f"/uploads/{up['id']}/remix",
                          json={"mode": "hybrid", "preset_key": "deephouse", "bpm_to": 96, "takes": 1})
    assert r.json()["remixes"][0]["bpm_to"] == 96

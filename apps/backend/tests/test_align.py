"""Lyric sync: match_lines is a pure matcher (tested on its own), the align job fills per-audio timings."""
from __future__ import annotations

from app.services import jobs
from app.services.align import match_lines

HEARD = [
    {"start": 0.0, "end": 3.0, "text": "Bolne se sach badalta nahi"},
    {"start": 3.5, "end": 7.0, "text": "khamosh rehne se koi samajhta nahi"},
    {"start": 8.0, "end": 11.0, "text": "duniya hai pyaar walon ki"},
]


def test_match_keeps_your_words_and_takes_whispers_times():
    known = "[Verse 1]\nBolne se sach badalta nahin\nKhamosh rehne se koi samajhta nahin\n\n[Chorus]\nDuniya hai pyaar walon ki"
    out = match_lines(known, HEARD)
    assert [o["text"] for o in out] == ["[Verse 1]", "Bolne se sach badalta nahin", "Khamosh rehne se koi samajhta nahin", "[Chorus]", "Duniya hai pyaar walon ki"]
    assert out[1]["start"] == 0.0 and out[2]["start"] == 3.5 and out[4]["start"] == 8.0
    assert out[0]["tag"] is True and out[0]["start"] == 0.0  # the tag highlights with its first line
    assert out[3]["start"] == 8.0


def test_unheard_lines_get_no_time_rather_than_a_guess():
    out = match_lines("Bolne se sach badalta nahin\nA line nobody sang at all here", HEARD)
    assert out[0]["start"] == 0.0
    assert "start" not in out[1]


def test_matching_never_goes_backwards():
    known = "duniya hai pyaar walon ki\nBolne se sach badalta nahi"  # deliberately out of order
    out = match_lines(known, HEARD)
    assert out[0]["start"] == 8.0
    assert "start" not in out[1]  # the earlier segment is behind us; no time beats a wrong time


def test_no_known_lyrics_falls_back_to_what_was_heard():
    assert match_lines("", HEARD) == [{"text": s["text"], "start": s["start"], "end": s["end"]} for s in HEARD]


async def test_align_a_take_fills_segments(client):
    song = (await client.post("/songs", json={"title": "S", "style": "pop", "lyrics": "[Verse]\nBolne se sach badalta nahi\nKhamosh rehne se koi samajhta nahi", "duration_s": 30})).json()
    await client.post(f"/songs/{song['id']}/generate", json={"takes": 1})
    await jobs.run_once()
    g = (await client.get(f"/songs/{song['id']}")).json()["generations"][0]
    assert g["lyrics_segments"] is None
    r = await client.post(f"/generations/{g['id']}/align")
    assert r.status_code == 202
    job = r.json()
    assert [s["key"] for s in job["progress"]["stages"]] == ["queued", "listening", "matching"]
    again = await client.post(f"/generations/{g['id']}/align")
    assert again.json()["id"] == job["id"]  # in-flight: one alignment, not two
    await jobs.run_once()
    done = (await client.get(f"/jobs/{job['id']}")).json()
    assert done["status"] == "done" and done["result"]["timed"] >= 1
    segs = (await client.get(f"/songs/{song['id']}")).json()["generations"][0]["lyrics_segments"]
    assert segs and segs[0]["text"] == "[Verse]" and any("start" in x for x in segs)


async def test_align_a_remix_uses_the_arrangements_lyrics(client):
    r = await client.post("/uploads", files={"file": ("x.wav", __import__("tests.test_remix", fromlist=["_wav_bytes"])._wav_bytes(), "audio/wav")}, data={"rights": "true", "vocal_language": "ur"})
    up = r.json()["upload"]
    await jobs.run_once()
    rr = await client.post(f"/uploads/{up['id']}/remix", json={"mode": "reimagine", "preset_key": "ballad", "takes": 1})
    await jobs.run_once()
    rid = rr.json()["remixes"][0]["id"]
    job = (await client.post(f"/remixes/{rid}/align")).json()
    await jobs.run_once()
    assert (await client.get(f"/jobs/{job['id']}")).json()["status"] == "done"
    segs = (await client.get(f"/remixes/{rid}")).json()["lyrics_segments"]
    assert segs and any("start" in x for x in segs)


def test_different_scripts_fall_back_to_an_approximate_spread_rather_than_nothing():
    """Our lyrics are romanized by product rule; Whisper returns Urdu script. Text can't match — the timeline still can."""
    heard = [{"start": 0.0, "end": 4.0, "text": "بولنے سے سچ بدلتا نہیں"},
             {"start": 4.0, "end": 8.0, "text": "خاموش رہنے سے کوئی سمجھتا نہیں"},
             {"start": 8.0, "end": 12.0, "text": "دنیا ہے پیار والوں کی"}]
    known = "[Verse 1]\nBolne se sach badalta nahin\nKhamosh rehne se koi samajhta nahin\nDuniya hai pyaar walon ki"
    out = match_lines(known, heard)
    assert [o["text"] for o in out][0] == "[Verse 1]"
    sung = [o for o in out if not o.get("tag")]
    assert len(sung) == 3 and all("start" in o for o in sung)
    assert all(o["approx"] is True for o in sung)          # honest about what it is
    assert [o["start"] for o in sung] == [0.0, 4.0, 8.0]   # in order, on the real timeline
    assert out[0]["start"] == 0.0                          # the tag still leads its section


def test_a_good_text_match_is_never_downgraded_to_approximate():
    out = match_lines("Bolne se sach badalta nahin\nkhamosh rehne se koi samajhta nahi", HEARD)
    assert all("approx" not in o for o in out)

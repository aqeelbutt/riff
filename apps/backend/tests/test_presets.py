"""Presets are data with a contract: unique keys, a caption, a tempo, no artist names."""
import re

from app.services.presets import CREATE_PRESETS, REMIX_PRESETS, all_presets

BANNED = re.compile(r"\b(jay-?z|linkin park|drake|eminem|beyonc|coldplay|arijit|atif)\b", re.I)


def test_keys_unique_and_shapes():
    for group in (CREATE_PRESETS, REMIX_PRESETS):
        keys = [p["key"] for p in group]
        assert len(keys) == len(set(keys))
        for p in group:
            assert p["label"] and len(p["caption"]) > 30 and isinstance(p["bpm"], int)
            assert not BANNED.search(p["caption"]), p["key"]
    for p in REMIX_PRESETS:
        assert 0.3 <= p["closeness"] <= 0.8


def test_boom_bap_is_present_on_both_surfaces():
    assert any(p["key"] == "boombap" for p in CREATE_PRESETS)
    assert any(p["key"] == "boombap" for p in REMIX_PRESETS)


async def test_presets_endpoint(client):
    r = await client.get("/presets")
    assert r.status_code == 200
    body = r.json()
    assert {"create", "remix", "moods", "languages"} <= set(body)
    assert any(l["code"] == "ur" for l in body["languages"])
    assert all_presets()["create"][0]["key"] == body["create"][0]["key"]


def test_reimagine_directions_are_arrangements_not_beats():
    from app.services.presets import REIMAGINE_DIRECTIONS
    keys = [d["key"] for d in REIMAGINE_DIRECTIONS]
    assert len(keys) == len(set(keys)) and "ballad" in keys and "anthem" in keys
    for d in REIMAGINE_DIRECTIONS:
        assert d["label"] and isinstance(d["bpm"], int) and len(d["caption"]) > 60
        assert not BANNED.search(d["caption"])
        # an arrangement names instruments and dynamics, not just a drum pattern
        assert any(w in d["caption"] for w in ("piano", "strings", "guitar", "harmonium", "Rhodes", "orchestral"))


async def test_presets_endpoint_serves_reimagine(client):
    body = (await client.get("/presets")).json()
    assert "reimagine" in body and any(d["key"] == "ballad" for d in body["reimagine"])

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

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


# --- the genres this studio is actually FOR --------------------------------------------------------
# Deep house, boom-bap and balearic are the house styles, so they carry an explicit contract rather than
# relying on someone noticing a regression by ear.

FOCUS = {
    "deephouse": {"bpm": (118, 128), "surfaces": ("create", "remix")},
    "boombap": {"bpm": (84, 96), "surfaces": ("create", "remix")},
    "balearic": {"bpm": (100, 120), "surfaces": ("create", "remix")},
}


def _by_key(group):
    return {p["key"]: p for p in group}


def test_focus_genres_exist_on_both_surfaces_at_a_sane_tempo():
    create, remix = _by_key(CREATE_PRESETS), _by_key(REMIX_PRESETS)
    for key, spec in FOCUS.items():
        for surface, group in (("create", create), ("remix", remix)):
            if surface not in spec["surfaces"]:
                continue
            assert key in group, f"{key} missing from {surface}"
            lo, hi = spec["bpm"]
            assert lo <= group[key]["bpm"] <= hi, f"{key} on {surface} is at {group[key]['bpm']} BPM"


def test_focus_genres_describe_the_mix_not_only_the_instruments():
    """Measured against a commercial reference our renders were dull up top (13.7% of energy above 8 kHz vs 22.1%).
    Asking the engine for air is the cheapest lever on that, so the captions must keep doing it."""
    air = ("airy", "bright", "crisp", "open top end", "wide", "spacious")
    for group in (CREATE_PRESETS, REMIX_PRESETS):
        for p in group:
            if p["key"] in FOCUS or p["key"].startswith("balearic"):
                assert any(w in p["caption"].lower() for w in air), f"{p['key']} says nothing about the mix"


def test_long_form_genres_ask_for_room():
    """Deep house and balearic are built on a long rise; at the 150s default they render as a fragment."""
    create = _by_key(CREATE_PRESETS)
    for key in ("deephouse", "balearic"):
        assert create[key].get("duration_s", 150) >= 240, f"{key} needs a longer default"


def test_balearic_is_reachable_for_the_songs_it_converts():
    """It exists to turn heartfelt rock / pop / R&B into drive music, so it must be a REMIX target too."""
    remix = _by_key(REMIX_PRESETS)
    assert "balearic" in remix and remix["balearic"]["closeness"] <= 0.6  # loose enough to actually restyle
    assert any(k.startswith("balearic") for k in remix)

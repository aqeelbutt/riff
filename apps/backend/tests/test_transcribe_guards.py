"""The transcription guards, tested without mlx-whisper (the script lazy-imports it).

These exist because a real upload — a 3:30 Urdu song mislabelled `en` — came back as six copies of
"Pakistan 345, base 7, 30 start push for Karachi" plus two half-translated lines, and Riff then built a
whole song out of it. Forced to the wrong language Whisper does not fail; it invents.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "app/services/audio/scripts/transcribe.py"
spec = importlib.util.spec_from_file_location("transcribe_script", SCRIPT)
tr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tr)


def seg(t: str, i: int) -> dict:
    return {"start": i * 4.0, "end": i * 4.0 + 3.5, "text": t}


def test_collapses_a_decode_loop_into_one_line():
    segs = [seg("Pakistan 345, base 7", i) for i in range(6)] + [seg("If you ask me", 6)]
    out, warns = tr._drop_loops(segs)
    assert [s["text"] for s in out] == ["Pakistan 345, base 7", "If you ask me"]
    assert warns and "decode loop" in warns[0]


def test_a_repeated_chorus_survives():
    """Negative control: a hook repeats through a song and must NOT be treated as a loop."""
    lines = ["Ek zindagi hai", "verse a", "Ek zindagi hai", "verse b", "Ek zindagi hai", "verse c", "Ek zindagi hai"]
    out, warns = tr._drop_loops([seg(t, i) for i, t in enumerate(lines)])
    assert len(out) == len(lines)
    assert warns == []


def test_a_held_line_merges_into_one_span_rather_than_two():
    out, _ = tr._drop_loops([seg("hold me", 0), seg("hold me", 1)])
    assert len(out) == 1 and out[0]["start"] == 0.0 and out[0]["end"] == 7.5


def test_two_back_to_back_repeats_are_not_flagged():
    """A doubled line is ordinary singing; only a run of them is a loop."""
    _, warns = tr._drop_loops([seg("oh oh", 0), seg("oh oh", 1), seg("next", 2)])
    assert warns == []


@pytest.mark.parametrize("a,b", [("Music", "music"), ("music!", "music"), ("  Music  ", "music")])
def test_normalisation_ignores_case_padding_and_punctuation(a, b):
    assert tr._norm(a) == tr._norm(b)


def test_collapses_a_word_stuttered_inside_one_segment():
    """Whisper loops mid-segment too — a real transcript came back with the same word 55 times in one line."""
    assert tr._collapse_within("आज " * 55 + "तो कुछ") == "आज आज तो कुछ"


def test_collapses_a_repeated_PHRASE_not_just_a_repeated_word():
    """Fixing the word-level loop only moved it: the next run of the same audio looped the phrase "आज तो" 32 times."""
    assert tr._collapse_within("आज तो " * 32 + "कुछ") == "आज तो आज तो कुछ"
    assert tr._collapse_within("कर दो कर दो कर दो कर दो") == "कर दो कर दो"


def test_a_line_sung_twice_is_preserved():
    """Negative control, and the one that matters most — repeating a line is what songs DO."""
    line = "ye dil mera kehta raha"
    assert tr._collapse_within(f"{line} {line}") == f"{line} {line}"
    assert tr._collapse_within("tu jo nahi to kuch bhi nahi") == "tu jo nahi to kuch bhi nahi"


def test_a_doubled_word_is_left_alone():
    """Negative control: repetition is a normal thing to sing."""
    assert tr._collapse_within("hey hey we are back") == "hey hey we are back"
    assert tr._collapse_within("na na na na na") == "na na"


def test_the_compression_threshold_is_whispers_own():
    """Sung lines on a real failing stem measured 1.4-2.0; its hallucinated loops hit 5.2 and 16.3."""
    assert tr.MAX_COMPRESSION_RATIO == 2.4

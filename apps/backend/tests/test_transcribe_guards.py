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

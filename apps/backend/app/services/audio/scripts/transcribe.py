#!/usr/bin/env python3
"""Lyrics from a VOCAL STEM with mlx-whisper → JSON {language, detected_language, segments, text, warnings}.
usage: transcribe.py <vocals.wav> <lang> [model]

Whisper fails in two loud ways on sung audio, and both used to reach the user as "lyrics":

1. Forced to the WRONG language it does not fail — it invents. An Urdu vocal decoded as `en` produced
   "Pakistan 345, base 7, 30 start push for Karachi" six times over. So we detect the language first and
   report the disagreement instead of trusting the picker blindly.
2. It loops. Whisper conditions on its own previous output, so once it repeats a line it can repeat it
   forever. `condition_on_previous_text=False` prevents most of it; the rest is collapsed here.
"""
import json
import re
import sys

MUSIC_ONLY = {"music", "موسیقی", "संगीत", "[music]", "(music)", "♪", "[موسیقى]", "you"}


def _norm(t: str) -> str:
    return re.sub(r"[^\w\s]", "", t.lower()).strip()


def _drop_loops(segs: list[dict]) -> tuple[list[dict], list[str]]:
    """Collapse a line repeated back-to-back into one held line — that shape is a decode loop, not singing.

    Deliberately does NOT drop a line by total count: a hook legitimately repeats five or six times in a song,
    and an earlier version of this guard would have deleted the chorus.
    """
    out: list[dict] = []
    collapsed = 0
    for s in segs:
        if out and _norm(out[-1]["text"]) == _norm(s["text"]):
            out[-1]["end"] = s["end"]
            collapsed += 1
            continue
        out.append(s)
    warn = [f"collapsed {collapsed} back-to-back repeats of the same line (a Whisper decode loop)"] if collapsed >= 3 else []
    return out, warn


def main(path: str, lang: str, model: str = "mlx-community/whisper-large-v3-mlx") -> None:
    import mlx_whisper  # imported here so the pure helpers above stay testable without the tools venv

    warnings: list[str] = []
    want = (lang or "").strip() or None

    # What language does the audio actually sound like? Cheap (30s window) and the answer is the whole ballgame.
    detected = None
    try:
        detected = mlx_whisper.transcribe(path, path_or_hf_repo=model, language=None, verbose=False,
                                          condition_on_previous_text=False, no_speech_threshold=0.6).get("language")
    except Exception:  # detection is best-effort; a failure must not cost you the transcription
        detected = None

    use = want
    if detected and want and detected != want:
        warnings.append(f"this sounds like '{detected}', not the '{want}' you picked — transcribed as '{detected}'")
        use = detected  # trust the audio over the dropdown: forcing the wrong language invents words
    elif detected and not want:
        use = detected

    r = mlx_whisper.transcribe(
        path, path_or_hf_repo=model, language=use, verbose=False,
        task="transcribe",                 # never "translate" — we want the words that were sung
        condition_on_previous_text=False,  # the repetition-loop guard
        no_speech_threshold=0.6,
        compression_ratio_threshold=2.4,
    )
    segs = [{"start": round(s["start"], 2), "end": round(s["end"], 2), "text": s["text"].strip()}
            for s in r["segments"] if s["text"].strip()]
    segs, w = _drop_loops(segs)
    warnings += w

    # Whisper's classic hallucination on near-silence, when it's the only thing found.
    if segs and {_norm(s["text"]) for s in segs} <= {_norm(m) for m in MUSIC_ONLY}:
        warnings.append("only found filler like 'music' — the vocal stem may be empty")
        segs = []

    # A real song has words roughly throughout. Two lines for three minutes means the decode failed.
    dur = max((s["end"] for s in segs), default=0.0)
    if segs and dur and len(segs) < max(3, dur / 45):
        warnings.append(f"only {len(segs)} line(s) across {int(dur)}s — the transcription looks incomplete; check the language")

    print(json.dumps({"language": use or r.get("language"), "detected_language": detected,
                      "segments": segs, "text": "\n".join(s["text"] for s in segs),
                      "warnings": warnings}, ensure_ascii=False))


if __name__ == "__main__":
    main(*sys.argv[1:])

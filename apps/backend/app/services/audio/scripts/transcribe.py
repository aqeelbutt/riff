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

# Languages that sound identical because they ARE the same spoken language written in a different script.
# Whisper cannot separate these from audio — there is nothing to hear; the difference is the writing system — so a
# "detection" that disagrees with the user's pick inside one of these groups is a coin toss, not evidence, and the
# pick has to win. Hindi/Urdu is the case this exists for (a Pakistani song came back in Devanagari). Other pairs
# behave the same way (Serbian/Croatian, Malay/Indonesian) but are left out until there is a song to test them on.
SAME_SPOKEN: list[set[str]] = [{"hi", "ur"}]


def _same_language(a: str, b: str) -> bool:
    return a == b or any({a, b} <= group for group in SAME_SPOKEN)


MUSIC_ONLY = {"music", "موسیقی", "संगीत", "[music]", "(music)", "♪", "[موسیقى]", "you"}

# Whisper's own hallucination signal, and far better than any text heuristic: `compression_ratio` is the gzip ratio
# of the decoded text, so a loop explodes it. On a real failing stem the sung lines measured 1.4-2.0 while the
# hallucinated ones hit 5.2 and 16.3. 2.4 is the threshold Whisper itself uses for its decoding fallback; here it
# also decides what reaches the user, because the fallback alone does not remove the segment from the output.
MAX_COMPRESSION_RATIO = 2.4


def _norm(t: str) -> str:
    return re.sub(r"[^\w\s]", "", t.lower()).strip()


def _collapse_within(text: str, keep: int = 2, max_phrase: int = 6) -> str:
    """Collapse a word OR PHRASE stuttered many times inside ONE segment down to `keep` copies.

    Whisper loops mid-segment, which the segment-level guard can't see. A real transcript came back with "आज"
    fifty-five times in one line, and after fixing that at word level the next run looped the PHRASE "आज तो"
    thirty-two times — so this has to work on n-grams, not just adjacent duplicate words. Two copies survive
    because singing a line twice is ordinary; only a longer run is a decode artefact.
    """
    toks = text.split()
    if len(toks) < 2 * keep + 1:
        return text
    out: list[str] = []
    i = 0
    while i < len(toks):
        best = 0  # length of the phrase that repeats from here, if any
        for p in range(1, max_phrase + 1):
            if i + 2 * p > len(toks):
                break
            phrase = [_norm(t) for t in toks[i:i + p]]
            reps = 1
            while all(_norm(t) == phrase[k] for k, t in enumerate(toks[i + reps * p: i + (reps + 1) * p])) \
                    and i + (reps + 1) * p <= len(toks):
                reps += 1
            if reps > keep:
                best = p
                break  # shortest repeating unit wins: "आज तो" over "आज तो आज तो"
        if best:
            p = best
            reps = 1
            while all(_norm(t) == _norm(toks[i + k]) for k, t in enumerate(toks[i + reps * p: i + (reps + 1) * p])) \
                    and i + (reps + 1) * p <= len(toks):
                reps += 1
            out += toks[i: i + p * keep]   # keep two copies of the phrase
            i += p * reps
        else:
            out.append(toks[i])
            i += 1
    return " ".join(out)


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
    if detected and want and not _same_language(detected, want):
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
    raw = [s for s in r["segments"] if s["text"].strip()]
    kept = [s for s in raw if (s.get("compression_ratio") or 0) <= MAX_COMPRESSION_RATIO]
    if len(kept) < len(raw):
        warnings.append(f"dropped {len(raw) - len(kept)} line(s) the model itself decoded as repetition, not speech")
    segs = [{"start": round(s["start"], 2), "end": round(s["end"], 2), "text": _collapse_within(s["text"].strip())}
            for s in kept]
    segs, w = _drop_loops(segs)
    warnings += w

    # Whisper labels instrumental passages "music" / "موسیقی" / "संगीत". That is never a lyric, so drop those lines
    # wherever they appear — an earlier version only dropped them when they were the ONLY thing found, so on a song
    # with real verses AND instrumental breaks the filler sailed through into the lyrics.
    filler = {_norm(m) for m in MUSIC_ONLY}
    if segs and {_norm(x["text"]) for x in segs} <= filler:
        warnings.append("only found filler like 'music' — the vocal stem may be empty")
        segs = []
    elif segs:
        dropped = [x for x in segs if _norm(x["text"]) in filler]
        if dropped:
            warnings.append(f"dropped {len(dropped)} line(s) of instrumental filler")
            segs = [x for x in segs if _norm(x["text"]) not in filler]

    # A real song has words roughly throughout. Two lines for three minutes means the decode failed.
    dur = max((s["end"] for s in segs), default=0.0)
    if segs and dur and len(segs) < max(3, dur / 45):
        warnings.append(f"only {len(segs)} line(s) across {int(dur)}s — the transcription looks incomplete; check the language")

    print(json.dumps({"language": use or r.get("language"), "detected_language": detected,
                      "segments": segs, "text": "\n".join(s["text"] for s in segs),
                      "warnings": warnings}, ensure_ascii=False))


if __name__ == "__main__":
    main(*sys.argv[1:])

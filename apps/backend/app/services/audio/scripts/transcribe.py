#!/usr/bin/env python3
"""Lyrics from a VOCAL STEM with mlx-whisper → JSON {language, segments:[{start,end,text}], text}. usage: transcribe.py <vocals.wav> <lang> [model]"""
import json
import sys

import mlx_whisper


def main(path: str, lang: str, model: str = "mlx-community/whisper-large-v3-mlx") -> None:
    r = mlx_whisper.transcribe(path, path_or_hf_repo=model, language=(lang or None), verbose=False)
    segs = [{"start": round(s["start"], 2), "end": round(s["end"], 2), "text": s["text"].strip()} for s in r["segments"] if s["text"].strip()]
    # drop Whisper's classic hallucination on near-silence ("music", "موسیقی", …) when it's the only thing found
    texts = {s["text"].lower() for s in segs}
    if texts and texts <= {"music", "موسیقی", "संगीत", "[music]", "(music)"}:
        segs = []
    print(json.dumps({"language": r.get("language") or lang, "segments": segs, "text": "\n".join(s["text"] for s in segs)}, ensure_ascii=False))


if __name__ == "__main__":
    main(*sys.argv[1:])

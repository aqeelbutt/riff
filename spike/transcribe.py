#!/usr/bin/env python3
"""Transcribe lyrics from a vocal stem (or full mix) with mlx-whisper. usage: transcribe.py <audio> <lang> <out_base>"""
import json, sys, time
import mlx_whisper
audio, lang, out = sys.argv[1], sys.argv[2], sys.argv[3]
t0 = time.time()
r = mlx_whisper.transcribe(audio, path_or_hf_repo="mlx-community/whisper-large-v3-mlx", language=lang, word_timestamps=False, verbose=False)
segs = [{"start": round(s["start"], 2), "end": round(s["end"], 2), "text": s["text"].strip()} for s in r["segments"] if s["text"].strip()]
json.dump({"language": r.get("language"), "elapsed_s": round(time.time() - t0, 1), "segments": segs}, open(out + ".json", "w"), ensure_ascii=False, indent=1)
open(out + ".txt", "w").write("\n".join(s["text"] for s in segs) + "\n")
print(f"{len(segs)} segments in {time.time()-t0:.0f}s → {out}.txt")

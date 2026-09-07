"""Post-render mastering: loudness-normalize (EBU R128 via ffmpeg loudnorm) and encode an MP3.

The engine's raw output sits at −17…−20 LUFS (Phase 0); streaming platforms expect about −14. Runs ffmpeg in a thread so
the event loop isn't blocked. If ffmpeg is missing or `mastering_enabled` is off, the raw WAV is kept and no MP3 is made.
"""
from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
from pathlib import Path

from app.core.config import get_settings

_LUFS_RE = re.compile(r"Output Integrated:\s*(-?[\d.]+) LUFS")


def _measure(wav_in: Path, target: float) -> dict | None:
    """Pass 1: ask loudnorm what the file actually measures, as JSON."""
    r = _run(["ffmpeg", "-v", "info", "-nostats", "-i", str(wav_in),
              "-af", f"loudnorm=I={target}:TP=-1:LRA=11:print_format=json", "-f", "null", "-"])
    try:
        blob = r.stderr[r.stderr.rindex("{"): r.stderr.rindex("}") + 1]
        d = json.loads(blob)
        return d if "input_i" in d else None
    except (ValueError, json.JSONDecodeError):
        return None


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


async def master(wav_in: Path) -> tuple[Path, Path | None, float | None]:
    """Returns (mastered_wav, mp3_or_None, measured_output_lufs_or_None)."""
    s = get_settings()
    if not s.mastering_enabled or shutil.which("ffmpeg") is None:
        return wav_in, None, None
    out_wav = wav_in.with_name(wav_in.stem + ".mastered.wav")
    out_mp3 = wav_in.with_name(wav_in.stem + ".mp3")
    target = s.mastering_target_lufs

    def _work() -> float | None:
        # TWO passes. Single-pass loudnorm is a DYNAMIC normalizer: it rides the level bar by bar and flattens the
        # music, which measured 4.9 LU of loudness range against 6.4 on a commercial reference — the builds and drops
        # this kind of music lives on were being ironed out. Measuring first and then applying `linear=true` makes it
        # one static gain instead, so the arrangement's own dynamics survive. Falls back to single-pass if pass 1
        # can't parse (an odd file, an old ffmpeg) — a flatter master beats no master.
        m0 = _measure(wav_in, target)
        if m0:
            filt = (f"loudnorm=I={target}:TP=-1:LRA=11:linear=true:"
                    f"measured_I={m0['input_i']}:measured_TP={m0['input_tp']}:"
                    f"measured_LRA={m0['input_lra']}:measured_thresh={m0['input_thresh']}:print_format=summary")
        else:
            filt = f"loudnorm=I={target}:TP=-1:LRA=11:print_format=summary"
        r = _run(["ffmpeg", "-v", "info", "-y", "-i", str(wav_in), "-af", filt, "-ar", "48000", str(out_wav)])
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg loudnorm failed: {r.stderr[-400:]}")
        m = _LUFS_RE.search(r.stderr)
        r2 = _run(["ffmpeg", "-v", "error", "-y", "-i", str(out_wav), "-codec:a", "libmp3lame", "-q:a", "2", str(out_mp3)])
        if r2.returncode != 0:
            raise RuntimeError(f"ffmpeg mp3 encode failed: {r2.stderr[-400:]}")
        return float(m.group(1)) if m else None

    lufs = await asyncio.to_thread(_work)
    return out_wav, out_mp3, lufs

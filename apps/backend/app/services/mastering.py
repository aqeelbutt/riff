"""Post-render mastering: loudness-normalize (EBU R128 via ffmpeg loudnorm) and encode an MP3.

The engine's raw output sits at −17…−20 LUFS (Phase 0); streaming platforms expect about −14. Runs ffmpeg in a thread so
the event loop isn't blocked. If ffmpeg is missing or `mastering_enabled` is off, the raw WAV is kept and no MP3 is made.
"""
from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
from pathlib import Path

from app.core.config import get_settings

_LUFS_RE = re.compile(r"Output Integrated:\s*(-?[\d.]+) LUFS")


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


async def master(wav_in: Path) -> tuple[Path, Path | None, float | None]:
    """Returns (mastered_wav, mp3_or_None, measured_output_lufs_or_None)."""
    s = get_settings()
    if not s.mastering_enabled or shutil.which("ffmpeg") is None:
        return wav_in, None, None
    out_wav = wav_in.with_name(wav_in.stem + ".mastered.wav")
    out_mp3 = wav_in.with_name(wav_in.stem + ".mp3")
    filt = f"loudnorm=I={s.mastering_target_lufs}:TP=-1:LRA=11:print_format=summary"

    def _work() -> float | None:
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

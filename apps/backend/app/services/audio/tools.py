"""Audio tools seam: stems (Demucs), lyrics (Whisper), analysis (librosa), vocal mix — real (subprocess into the tools venv)
or fake (instant, deterministic; the test suite and machines without the venv). One GPU workload at a time: the job runner
already serializes; these are the only other Metal clients and they only ever run inside a job."""
from __future__ import annotations

import asyncio
import json
import math
import struct
import wave
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings

SCRIPTS = Path(__file__).resolve().parent / "scripts"


class ToolError(RuntimeError):
    pass


@dataclass
class Analysis:
    duration_s: float
    bpm: float
    key: str
    lufs: float


class RealAudioTools:
    name = "real"

    def __init__(self) -> None:
        s = get_settings()
        self.python = Path(s.audio_tools_python)
        self.whisper_model = s.whisper_model
        self.demucs_model = s.demucs_model

    async def _run(self, script: str, *args: str, timeout: int = 1800) -> dict:
        proc = await asyncio.create_subprocess_exec(str(self.python), str(SCRIPTS / script), *args,
                                                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            proc.kill()
            raise ToolError(f"{script} timed out") from exc
        if proc.returncode != 0:
            raise ToolError(f"{script} failed: {err.decode(errors='replace')[-800:]}")
        line = out.decode().strip().splitlines()[-1] if out.strip() else "{}"
        return json.loads(line)

    async def analyze(self, path: Path) -> Analysis:
        d = await self._run("analyze.py", str(path), timeout=300)
        return Analysis(d["duration_s"], d["bpm"], d["key"], d["lufs"])

    async def separate(self, path: Path, out_dir: Path) -> dict[str, dict]:
        return (await self._run("separate.py", str(path), str(out_dir), self.demucs_model))["stems"]

    async def transcribe(self, vocals: Path, lang: str) -> dict:
        return await self._run("transcribe.py", str(vocals), lang or "", self.whisper_model, timeout=900)

    async def vocal_mix(self, cfg: dict) -> dict:
        return await self._run("vocal_mix.py", json.dumps(cfg), timeout=900)


def _sine_wav(path: Path, seconds: float = 3.0, freq: float = 220.0, sr: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(4000 * math.sin(2 * math.pi * freq * n / sr))) for n in range(int(sr * seconds))))


class FakeAudioTools:
    """Instant stand-ins with the same contract; writes tiny valid WAVs so downstream streaming works."""

    name = "fake"
    lyrics_text = "Bolne se sach badalta nahi\nKhamosh rehne se koi samajhta nahi"

    async def analyze(self, path: Path) -> Analysis:
        return Analysis(duration_s=3.0, bpm=126.0, key="G major", lufs=-11.6)

    async def separate(self, path: Path, out_dir: Path) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for k, share, f in (("vocals", 0.25, 440), ("drums", 0.30, 110), ("bass", 0.25, 55), ("other", 0.20, 330), ("instrumental", None, 165)):
            p = out_dir / f"{k}.wav"; _sine_wav(p, freq=f); out[k] = {"path": str(p), "energy_share": share}
        return out

    async def transcribe(self, vocals: Path, lang: str) -> dict:
        lines = self.lyrics_text.splitlines()
        return {"language": lang or "en", "segments": [{"start": i * 4.0, "end": i * 4.0 + 3.5, "text": t} for i, t in enumerate(lines)], "text": "\n".join(lines)}

    async def vocal_mix(self, cfg: dict) -> dict:
        _sine_wav(Path(cfg["out"]), freq=262)
        return {"out": cfg["out"], "lufs": -14.0, "duration_s": 3.0}


_override = None


def set_audio_tools(t) -> None:
    global _override
    _override = t


def get_audio_tools():
    if _override is not None:
        return _override
    s = get_settings()
    if s.audio_tools == "fake" or (s.audio_tools == "auto" and not Path(s.audio_tools_python).exists()):
        return FakeAudioTools()
    return RealAudioTools()

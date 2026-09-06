"""FakeProvider — deterministic, instant, no engine. Used by the test suite and `MUSIC_PROVIDER=fake`.

Writes a short valid WAV (a quiet sine at the requested BPM's beat) so downstream code (mastering, streaming, waveform)
exercises real audio paths.
"""
from __future__ import annotations

import math
import struct
import time
import uuid
import wave

from app.services.music.base import ProgressCb, ProviderError, RenderRequest, RenderResult, RenderedTake


class FakeProvider:
    name = "fake"
    fail_next: int = 0  # tests set this to simulate a crashed engine

    async def health(self) -> dict:
        return {"ok": True, "service": "fake"}

    async def render(self, req: RenderRequest, on_progress: ProgressCb | None = None) -> RenderResult:
        if self.fail_next > 0:
            self.fail_next -= 1
            raise ProviderError("simulated engine failure")
        t0 = time.time()
        if on_progress:
            await on_progress("rendering")
        req.out_dir.mkdir(parents=True, exist_ok=True)
        takes = []
        sr, dur = 16000, min(req.duration_s, 3)  # short: tests must stay fast
        bpm = req.bpm or 120
        for i in range(1, max(1, req.takes) + 1):
            seed = (req.seeds[i - 1] if req.seeds and i - 1 < len(req.seeds) else 1000 + i)
            path = req.out_dir / f"take-{i}-{uuid.uuid4().hex[:8]}.wav"
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
                frames = bytearray()
                for n in range(sr * dur):
                    t = n / sr
                    beat = 1.0 if (t * bpm / 60) % 1 < 0.1 else 0.3
                    frames += struct.pack("<h", int(3000 * beat * math.sin(2 * math.pi * (220 + 10 * seed % 7) * t)))
                w.writeframes(bytes(frames))
            takes.append(RenderedTake(path=path, seed=str(seed), model="fake-v1", metas={"bpm": bpm, "duration": dur}))
        if on_progress:
            await on_progress("decoding")
        return RenderResult(takes=takes, provider=self.name, render_seconds=round(time.time() - t0, 3))

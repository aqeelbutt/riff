"""The MusicProvider seam. The product talks ONLY to this; ACE-Step (local) and any hosted engine plug in behind it."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

ProgressCb = Callable[[str], Awaitable[None]]  # stage key: queued | rendering | decoding | mastering


@dataclass
class RenderRequest:
    style: str  # engine caption
    lyrics: str = ""  # empty ⇒ instrumental (engine semantics)
    duration_s: int = 150
    bpm: int | None = None  # ALWAYS pass when known — the caption's "118 BPM" is not honored
    key: str | None = None
    vocal_language: str = "en"
    takes: int = 2
    seeds: list[int] | None = None
    quality: str = "fast"  # fast | studio
    instrumental: bool = False
    out_dir: Path = field(default_factory=lambda: Path("."))


@dataclass
class RenderedTake:
    path: Path
    seed: str | None
    model: str | None
    metas: dict


@dataclass
class RenderResult:
    takes: list[RenderedTake]
    provider: str
    render_seconds: float
    raw: dict = field(default_factory=dict)


class MusicProvider(Protocol):
    name: str

    async def health(self) -> dict: ...

    async def render(self, req: RenderRequest, on_progress: ProgressCb | None = None) -> RenderResult: ...


class ProviderError(RuntimeError):
    """The engine failed or vanished mid-render. Retryable by the job runner."""

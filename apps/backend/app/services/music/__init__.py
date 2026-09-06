"""Provider registry: `get_provider()` returns the configured MusicProvider (acestep | fake)."""
from __future__ import annotations

from app.core.config import get_settings
from app.services.music.base import MusicProvider, ProviderError, RenderRequest, RenderResult, RenderedTake

_override: MusicProvider | None = None


def set_provider(p: MusicProvider | None) -> None:
    """Tests inject a FakeProvider here; None restores the configured one."""
    global _override
    _override = p


def get_provider() -> MusicProvider:
    if _override is not None:
        return _override
    name = get_settings().music_provider
    if name == "fake":
        from app.services.music.fake import FakeProvider
        return FakeProvider()
    from app.services.music.acestep import ACEStepProvider
    return ACEStepProvider()


__all__ = ["get_provider", "set_provider", "MusicProvider", "ProviderError", "RenderRequest", "RenderResult", "RenderedTake"]

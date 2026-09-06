"""LocalFS storage (V1). Paths stored in the DB are RELATIVE to media_root so an S3 provider (V2) is a drop-in."""
from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings


class LocalStorage:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or get_settings().media_root).resolve()

    def generation_dir(self, song_id: str, batch_id: str) -> Path:
        d = self.root / "generations" / str(song_id) / str(batch_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def relative(self, path: Path) -> str:
        return str(Path(path).resolve().relative_to(self.root))

    def absolute(self, rel: str) -> Path:
        p = (self.root / rel).resolve()
        if self.root not in p.parents and p != self.root:
            raise ValueError("path escapes media root")
        return p


def get_storage() -> LocalStorage:
    return LocalStorage()

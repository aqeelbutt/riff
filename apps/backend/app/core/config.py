"""Application settings, loaded from the environment / a `.env` file (mirrors the PursuitAI pattern).

Every field here MUST also appear in `apps/backend/.env.example` with a one-line comment.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = BACKEND_ROOT.parent.parent


def _find_env_file() -> str:
    for p in (Path.cwd() / ".env", BACKEND_ROOT / ".env"):
        if p.exists():
            return str(p)
    return ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_find_env_file(), env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Riff"
    app_env: str = "development"  # development | test | production
    debug: bool = False

    # Postgres (docker-compose maps it to 5433 so it never collides with another project's 5432)
    database_url: str = "postgresql+asyncpg://riff:riff_dev@localhost:5433/riff"

    # Music engine sidecar (ACE-Step REST) and which provider the app talks to
    music_provider: str = "acestep"  # acestep | fake
    engine_url: str = "http://127.0.0.1:8001"
    engine_timeout_s: int = 900  # a 10-minute song on a slow Mac can take this long
    engine_default_model: str = "acestep-v15-turbo"
    engine_studio_model: str = "acestep-v15-sft"

    # Where rendered audio lives (LocalFS storage; S3 is a V2 provider)
    media_root: str = str(REPO_ROOT / "var" / "media")

    # Jobs
    worker_enabled: bool = True  # the in-process worker; disabled in tests, which drive jobs by hand
    job_poll_seconds: float = 1.0
    job_max_attempts: int = 3
    job_stale_seconds: int = 300  # a job with no heartbeat for this long is re-queued by the reaper

    # Mastering (ffmpeg loudnorm). Off = ship the engine's raw WAV.
    mastering_enabled: bool = True
    mastering_target_lufs: float = -14.0

    # Claude (lyrics). Empty key ⇒ the fake lyrics provider (dev without a key, and the test suite).
    anthropic_api_key: str = ""
    lyrics_provider: str = "auto"  # auto (claude if a key is set, else fake) | claude | fake
    claude_model: str = "claude-opus-5"
    claude_effort: str = "high"  # low | medium | high | xhigh | max

    # CORS for the web app
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()

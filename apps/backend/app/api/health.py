"""Health: API + DB + engine + worker, in one call, for the web status page and `riff engine status`."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.main_state import state
from app.services.jobs import db_ping
from app.services.music import get_provider

router = APIRouter(tags=["health"])
APP_VERSION = "1.1.0"


@router.get("/")
@router.get("/health")
async def health() -> dict:
    s = get_settings()
    try:
        db_ok = await db_ping()
    except Exception as exc:  # noqa: BLE001
        db_ok = False
    provider = get_provider()
    return {
        "app": s.app_name, "version": APP_VERSION, "env": s.app_env,
        "db": {"ok": db_ok},
        "engine": {"provider": provider.name, **(await provider.health())},
        "worker": {"enabled": s.worker_enabled, "running": state.worker_task is not None and not state.worker_task.done()},
    }

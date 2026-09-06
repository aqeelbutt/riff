"""Riff API. `uvicorn app.main:app --reload --port 8010`."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.services.generation  # noqa: F401 — registers the `render` job handler
import app.services.remix  # noqa: F401 — registers `analyze` + `remix`
from app.api import generations, health, jobs, lyrics, presets, remixes, songs, uploads
import app.services.ai.telemetry  # noqa: F401 — registers the AiCallTelemetry table
from app.core.config import get_settings
from app.main_state import state
from app.services.jobs import worker_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.worker_enabled:
        state.stop = asyncio.Event()
        state.worker_task = asyncio.create_task(worker_loop(state.stop), name="riff-worker")
    yield
    if state.worker_task:
        state.stop.set()
        try:
            await asyncio.wait_for(state.worker_task, timeout=5)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            state.worker_task.cancel()


app = FastAPI(title="Riff API", version=health.APP_VERSION, lifespan=lifespan, redirect_slashes=False)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"], allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(songs.router)
app.include_router(jobs.router)
app.include_router(generations.router)
app.include_router(presets.router)
app.include_router(lyrics.router)
app.include_router(uploads.router)
app.include_router(remixes.router)

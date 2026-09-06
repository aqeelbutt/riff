"""Test fixtures (PursuitAI conventions): a dedicated `riff_test` DB, create_all, truncate between tests, FakeProvider,
and the job-runner's own sessions redirected to the test engine.

run_tests.sh exports APP_ENV=test MUSIC_PROVIDER=fake WORKER_ENABLED=false MASTERING_ENABLED=false + the test DATABASE_URL
BEFORE anything imports `app`, so `get_settings()` already points at the test DB.
"""
from __future__ import annotations

import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("MUSIC_PROVIDER", "fake")
os.environ.setdefault("WORKER_ENABLED", "false")
os.environ.setdefault("MASTERING_ENABLED", "false")
os.environ.setdefault("LYRICS_PROVIDER", "fake")
os.environ.setdefault("AUDIO_TOOLS", "fake")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://riff:riff_dev@localhost:5433/riff_test")

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.core import database as db  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.services import jobs as jobs_mod  # noqa: E402
from app.services.music import set_provider  # noqa: E402
from app.services.music.fake import FakeProvider  # noqa: E402
from app.services.ai import telemetry as telemetry_mod  # noqa: E402
from app.services.ai.lyrics import FakeLyrics, set_lyrics_provider  # noqa: E402
from app.services.audio.tools import FakeAudioTools, set_audio_tools  # noqa: E402

TEST_URL = os.environ["DATABASE_URL"]
ADMIN_URL = TEST_URL.rsplit("/", 1)[0] + "/riff"
test_engine = create_async_engine(TEST_URL, poolclass=NullPool)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def _ensure_db() -> None:
    admin = create_async_engine(ADMIN_URL, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    async with admin.connect() as c:
        if not (await c.execute(text("SELECT 1 FROM pg_database WHERE datname='riff_test'"))).scalar():
            await c.execute(text("CREATE DATABASE riff_test"))
    await admin.dispose()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _schema():
    await _ensure_db()
    async with test_engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)
        for e in ("song_status", "job_status", "upload_status", "remix_mode"):
            await c.execute(text(f"DROP TYPE IF EXISTS {e} CASCADE"))
        await c.run_sync(Base.metadata.create_all)
    yield
    await test_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    yield
    async with test_engine.begin() as c:
        await c.execute(text("TRUNCATE TABLE remixes, stems, uploads, generations, jobs, songs, users, ai_call_telemetry RESTART IDENTITY CASCADE"))


@pytest.fixture(autouse=True)
def _redirect_jobs_to_test_engine(monkeypatch):
    """jobs.py opens its own sessions via app.core.database.async_session → point them at the test engine."""
    monkeypatch.setattr(db, "async_session", TestSession)
    monkeypatch.setattr(jobs_mod.db, "async_session", TestSession)
    monkeypatch.setattr(telemetry_mod.db, "async_session", TestSession)


@pytest.fixture(autouse=True)
def fake_lyrics():
    p = FakeLyrics()
    set_lyrics_provider(p)
    yield p
    set_lyrics_provider(None)


@pytest.fixture(autouse=True)
def fake_tools():
    t = FakeAudioTools()
    set_audio_tools(t)
    yield t
    set_audio_tools(None)


@pytest.fixture(autouse=True)
def fake_provider():
    p = FakeProvider()
    set_provider(p)
    yield p
    set_provider(None)


async def _override_get_db():
    async with TestSession() as s:
        yield s


@pytest_asyncio.fixture
async def client():
    from app.core.database import get_db
    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def session():
    async with TestSession() as s:
        yield s

"""Async SQLAlchemy engine + session (PursuitAI conventions: pool_pre_ping, small pool, FOR UPDATE-capable dialect)."""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,
    pool_recycle=240,
    pool_timeout=10,
)

if engine.dialect.name not in {"postgresql", "postgres"}:
    raise RuntimeError("Riff requires Postgres: the job runner relies on SELECT … FOR UPDATE SKIP LOCKED")

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        yield session

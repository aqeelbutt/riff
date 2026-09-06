"""AI call telemetry — one row per Claude call (success OR failure), own short session (PursuitAI `ai_call_telemetry`).

Cost is computed from a small price table so the Settings page can show "Claude spend this month" from day one.
"""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core import database as db
from app.core.database import Base

log = logging.getLogger(__name__)

# USD per 1M tokens: (input, output, cache_read). Keep in step with the Claude pricing page.
PRICES = {
    "claude-opus-5": (5.0, 25.0, 0.5),
    "claude-sonnet-5": (2.0, 10.0, 0.2),
    "claude-haiku-4-5": (1.0, 5.0, 0.1),
    "claude-fable-5-1": (10.0, 50.0, 1.0),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int, cache_read_tokens: int = 0) -> float:
    i, o, c = PRICES.get(model, (5.0, 25.0, 0.5))
    return round((input_tokens - cache_read_tokens) * i / 1e6 + output_tokens * o / 1e6 + cache_read_tokens * c / 1e6, 6)


class AiCallTelemetry(Base):
    __tablename__ = "ai_call_telemetry"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    feature: Mapped[str] = mapped_column(String(40), index=True)  # lyrics_brief | lyrics_write | lyrics_section
    model: Mapped[str] = mapped_column(String(60))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    elapsed_ms: Mapped[int] = mapped_column(Integer, default=0)
    ok: Mapped[bool] = mapped_column(default=True)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


async def record(feature: str, model: str, *, user_id: uuid.UUID | None, elapsed_ms: int, ok: bool,
                 input_tokens: int = 0, output_tokens: int = 0, cache_read_tokens: int = 0, error: str | None = None) -> None:
    try:
        async with db.async_session() as s:
            s.add(AiCallTelemetry(user_id=user_id, feature=feature, model=model, input_tokens=input_tokens, output_tokens=output_tokens,
                                  cache_read_tokens=cache_read_tokens, cost_usd=cost_usd(model, input_tokens, output_tokens, cache_read_tokens),
                                  elapsed_ms=elapsed_ms, ok=ok, error=(error or None) and error[:2000]))
            await s.commit()
    except Exception:  # noqa: BLE001 — telemetry must never break the feature
        log.exception("telemetry write failed")


@asynccontextmanager
async def timed(feature: str, model: str, user_id: uuid.UUID | None):
    """`async with timed(...) as t:` → set t["usage"] from the response; failures are recorded too."""
    t0 = time.time()
    box: dict = {"usage": None}
    try:
        yield box
    except Exception as exc:
        await record(feature, model, user_id=user_id, elapsed_ms=int((time.time() - t0) * 1000), ok=False, error=f"{type(exc).__name__}: {exc}")
        raise
    u = box.get("usage")
    await record(feature, model, user_id=user_id, elapsed_ms=int((time.time() - t0) * 1000), ok=True,
                 input_tokens=getattr(u, "input_tokens", 0) or 0, output_tokens=getattr(u, "output_tokens", 0) or 0,
                 cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0)

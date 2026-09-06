"""Process-level state (the worker task) — separate module so routers can import it without importing main."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class _State:
    worker_task: asyncio.Task | None = None
    stop: asyncio.Event = field(default_factory=asyncio.Event)


state = _State()

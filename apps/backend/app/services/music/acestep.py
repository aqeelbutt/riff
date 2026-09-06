"""ACE-Step 1.5 REST provider (the local sidecar on :8001). Port of spike/run_spike.py."""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

from app.core.config import get_settings
from app.services.music.base import ProgressCb, ProviderError, RenderRequest, RenderResult, RenderedTake


class ACEStepProvider:
    name = "acestep"

    def __init__(self, base_url: str | None = None, timeout_s: int | None = None) -> None:
        s = get_settings()
        self.base_url = (base_url or s.engine_url).rstrip("/")
        self.timeout_s = timeout_s or s.engine_timeout_s
        self.default_model = s.engine_default_model
        self.studio_model = s.engine_studio_model

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=5) as c:
                r = await c.get("/health")
                r.raise_for_status()
                return {"ok": True, **(r.json().get("data") or {})}
        except Exception as exc:  # noqa: BLE001 — any failure = engine down
            return {"ok": False, "error": str(exc)[:200]}

    def _body(self, req: RenderRequest) -> dict:
        studio = req.quality == "studio"
        body = {
            "prompt": req.style,
            "lyrics": "" if req.instrumental else (req.lyrics or ""),
            "audio_duration": req.duration_s,
            "inference_steps": 50 if studio else 8,
            "model": self.studio_model if studio else self.default_model,
            "thinking": False,  # Claude is the planner; the 5Hz LM is off the critical path
            "batch_size": max(1, min(8, req.takes)),
            "audio_format": "wav",
            "use_random_seed": not req.seeds,
            "vocal_language": req.vocal_language or "en",
            "instrumental": req.instrumental,
        }
        if not studio:
            body["shift"] = 3.0  # turbo needs shift=3 (not auto-corrected)
        if req.seeds:
            body["seed"] = req.seeds[0]
        if req.bpm:
            body["bpm"] = int(req.bpm)
        if req.key:
            body["key"] = req.key
        return body

    async def render(self, req: RenderRequest, on_progress: ProgressCb | None = None) -> RenderResult:
        t0 = time.time()
        body = self._body(req)
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=httpx.Timeout(self.timeout_s, connect=10)) as c:
                r = await c.post("/release_task", json=body)
                r.raise_for_status()
                task_id = r.json()["data"]["task_id"]
                if on_progress:
                    await on_progress("rendering")
                item = await self._poll(c, task_id)
                if on_progress:
                    await on_progress("decoding")
                result = item.get("result")
                if isinstance(result, str):
                    result = json.loads(result)
                audios = result if isinstance(result, list) else [result]
                req.out_dir.mkdir(parents=True, exist_ok=True)
                takes: list[RenderedTake] = []
                for i, a in enumerate(audios, 1):
                    url = a.get("file")
                    ext = Path(parse_qs(urlparse(url).query).get("path", [""])[0]).suffix or ".wav"
                    dest = req.out_dir / f"take-{i}-{uuid.uuid4().hex[:8]}{ext}"
                    async with c.stream("GET", url) as resp:
                        resp.raise_for_status()
                        with open(dest, "wb") as f:
                            async for chunk in resp.aiter_bytes():
                                f.write(chunk)
                    seeds = str(a.get("seed_value") or "").split(",")
                    takes.append(RenderedTake(path=dest, seed=(seeds[i - 1] if i - 1 < len(seeds) else seeds[0]).strip() or None,
                                              model=a.get("dit_model"), metas=a.get("metas") or {}))
        except httpx.HTTPError as exc:
            raise ProviderError(f"engine request failed: {exc}") from exc
        return RenderResult(takes=takes, provider=self.name, render_seconds=round(time.time() - t0, 1), raw={"request": body})

    async def _poll(self, c: httpx.AsyncClient, task_id: str) -> dict:
        deadline = time.time() + self.timeout_s
        while time.time() < deadline:
            r = await c.post("/query_result", json={"task_id_list": [task_id]})
            r.raise_for_status()
            items = r.json().get("data") or []
            item = items[0] if items else {}
            if item.get("status") == 1:
                return item
            if item.get("status") == 2:
                raise ProviderError(f"engine task failed: {json.dumps(item)[:500]}")
            await asyncio.sleep(2)
        raise ProviderError("engine task timed out")

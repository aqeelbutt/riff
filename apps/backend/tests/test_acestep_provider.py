"""Contract test for the ACE-Step provider against a mocked sidecar with the REAL API shape from Phase 0."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.services.music.acestep import ACEStepProvider
from app.services.music.base import ProviderError, RenderRequest


def _mock_engine(calls: list, fail: bool = False):
    polls = {"n": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, json.loads(request.content) if request.content else None))
        if request.url.path == "/release_task":
            return httpx.Response(200, json={"data": {"task_id": "t1"}, "code": 200})
        if request.url.path == "/query_result":
            polls["n"] += 1
            if fail:
                return httpx.Response(200, json={"data": [{"status": 2, "result": "boom"}]})
            if polls["n"] < 2:
                return httpx.Response(200, json={"data": [{"status": 0}]})
            result = [{"file": "/v1/audio?path=%2Ftmp%2Fa.wav", "status": 1, "seed_value": "111,222", "dit_model": "acestep-v15-turbo",
                       "metas": {"bpm": 118, "duration": 30, "keyscale": "D major"}},
                      {"file": "/v1/audio?path=%2Ftmp%2Fb.wav", "status": 1, "seed_value": "111,222", "dit_model": "acestep-v15-turbo",
                       "metas": {"bpm": 118, "duration": 30}}]
            return httpx.Response(200, json={"data": [{"status": 1, "result": json.dumps(result)}]})
        if request.url.path == "/v1/audio":
            return httpx.Response(200, content=b"RIFF....WAVEfake", headers={"content-type": "audio/wav"})
        if request.url.path == "/health":
            return httpx.Response(200, json={"data": {"status": "ok", "loaded_model": "acestep-v15-turbo"}})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.fixture
def patched_client(monkeypatch):
    def _make(transport):
        real = httpx.AsyncClient

        def factory(*a, **kw):
            kw["transport"] = transport
            return real(*a, **kw)
        monkeypatch.setattr(httpx, "AsyncClient", factory)
    return _make


async def test_render_sends_engine_contract_and_downloads_takes(tmp_path: Path, patched_client, monkeypatch):
    monkeypatch.setattr("app.services.music.acestep.asyncio.sleep", _no_sleep)
    calls: list = []
    patched_client(_mock_engine(calls))
    p = ACEStepProvider(base_url="http://engine")
    stages: list[str] = []

    async def prog(s):
        stages.append(s)

    req = RenderRequest(style="deep house", lyrics="[Verse]\nhi", duration_s=30, bpm=118, vocal_language="ur", takes=2, out_dir=tmp_path)
    res = await p.render(req, on_progress=prog)

    body = next(b for m, path, b in calls if path == "/release_task")
    # the Phase 0 lessons, pinned:
    assert body["bpm"] == 118 and body["vocal_language"] == "ur" and body["thinking"] is False
    assert body["shift"] == 3.0 and body["inference_steps"] == 8 and body["model"] == "acestep-v15-turbo"
    assert body["batch_size"] == 2 and body["audio_format"] == "wav" and body["lyrics"] == "[Verse]\nhi"
    assert stages == ["rendering", "decoding"]
    assert len(res.takes) == 2 and [t.seed for t in res.takes] == ["111", "222"]
    assert res.takes[0].metas["keyscale"] == "D major" and res.takes[0].path.exists() and res.takes[0].path.suffix == ".wav"
    assert res.provider == "acestep"


async def test_studio_quality_switches_model_and_steps(tmp_path: Path, patched_client, monkeypatch):
    monkeypatch.setattr("app.services.music.acestep.asyncio.sleep", _no_sleep)
    calls: list = []
    patched_client(_mock_engine(calls))
    await ACEStepProvider(base_url="http://engine").render(RenderRequest(style="x", quality="studio", takes=1, out_dir=tmp_path))
    body = next(b for m, path, b in calls if path == "/release_task")
    assert body["model"] == "acestep-v15-sft" and body["inference_steps"] == 50 and "shift" not in body


async def test_instrumental_sends_empty_lyrics(tmp_path: Path, patched_client, monkeypatch):
    monkeypatch.setattr("app.services.music.acestep.asyncio.sleep", _no_sleep)
    calls: list = []
    patched_client(_mock_engine(calls))
    await ACEStepProvider(base_url="http://engine").render(RenderRequest(style="x", lyrics="[Verse] words", instrumental=True, takes=1, out_dir=tmp_path))
    body = next(b for m, path, b in calls if path == "/release_task")
    assert body["lyrics"] == "" and body["instrumental"] is True


async def test_engine_task_failure_raises_provider_error(tmp_path: Path, patched_client, monkeypatch):
    monkeypatch.setattr("app.services.music.acestep.asyncio.sleep", _no_sleep)
    patched_client(_mock_engine([], fail=True))
    with pytest.raises(ProviderError):
        await ACEStepProvider(base_url="http://engine").render(RenderRequest(style="x", takes=1, out_dir=tmp_path))


async def test_health_reports_down_when_unreachable():
    p = ACEStepProvider(base_url="http://127.0.0.1:1")
    h = await p.health()
    assert h["ok"] is False and "error" in h


async def _no_sleep(_):
    return None

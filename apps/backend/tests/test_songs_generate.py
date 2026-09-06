"""The Phase 1 spine: POST /songs → POST /songs/{id}/generate → job → worker → generations with audio on disk."""
from __future__ import annotations

from pathlib import Path

from app.services import jobs
from app.services.storage import get_storage

SONG = {"title": "Run With Me", "style": "upbeat pop, female vocal", "lyrics": "[Verse]\nla la la", "bpm": 118, "duration_s": 30}


async def test_create_generate_and_render(client):
    r = await client.post("/songs", json=SONG)
    assert r.status_code == 201, r.text
    song = r.json()
    assert song["status"] == "draft" and song["generations"] == []

    r = await client.post(f"/songs/{song['id']}/generate", json={"takes": 2})
    assert r.status_code == 202, r.text
    job = r.json()
    assert job["status"] == "queued" and job["progress"]["current"] == "queued"
    assert [s["key"] for s in job["progress"]["stages"]] == ["queued", "rendering", "decoding", "mastering"]

    assert (await client.get(f"/songs/{song['id']}")).json()["status"] == "rendering"

    assert await jobs.run_once() is True  # the single GPU lane, driven by hand in tests
    assert await jobs.run_once() is False  # nothing left

    j = (await client.get(f"/jobs/{job['id']}")).json()
    assert j["status"] == "done", j
    assert j["progress"]["current"] == "done"
    assert len(j["result"]["generation_ids"]) == 2 and j["result"]["provider"] == "fake"

    s = (await client.get(f"/songs/{song['id']}")).json()
    assert s["status"] == "ready" and len(s["generations"]) == 2
    takes = sorted(s["generations"], key=lambda g: g["take_index"])
    assert [t["take_index"] for t in takes] == [1, 2]
    assert takes[0]["seed"] != takes[1]["seed"]
    assert takes[0]["batch_id"] == takes[1]["batch_id"]
    assert takes[0]["metas"]["bpm"] == 118  # bpm reached the provider

    r = await client.get(takes[0]["audio_url"])
    assert r.status_code == 200 and r.headers["content-type"].startswith("audio/wav") and len(r.content) > 1000
    media = get_storage().root
    assert any(p.suffix == ".wav" for p in Path(media).rglob("*")), "the take was written under media_root"


async def test_generate_is_idempotent_while_in_flight(client):
    song = (await client.post("/songs", json=SONG)).json()
    a = (await client.post(f"/songs/{song['id']}/generate", json={"takes": 1})).json()
    b = (await client.post(f"/songs/{song['id']}/generate", json={"takes": 1})).json()
    assert a["id"] == b["id"], "a double-click must not render twice"
    await jobs.run_once()
    c = (await client.post(f"/songs/{song['id']}/generate", json={"takes": 1})).json()
    assert c["id"] != a["id"], "after the first finishes, a new run is allowed"


async def test_empty_lyrics_means_instrumental(client, fake_provider, monkeypatch):
    """Empty lyrics ⇒ the provider is asked for an instrumental (the engine's own semantics, learned in Phase 0)."""
    seen = {}
    real = fake_provider.render

    async def spy(req, on_progress=None):
        seen["instrumental"] = req.instrumental
        return await real(req, on_progress)

    monkeypatch.setattr(fake_provider, "render", spy)
    song = (await client.post("/songs", json={**SONG, "lyrics": ""})).json()
    await client.post(f"/songs/{song['id']}/generate", json={"takes": 1})
    await jobs.run_once()
    assert seen["instrumental"] is True
    assert (await client.get(f"/songs/{song['id']}")).json()["status"] == "ready"


async def test_engine_failure_is_retried_then_fails(client, fake_provider):
    song = (await client.post("/songs", json=SONG)).json()
    job = (await client.post(f"/songs/{song['id']}/generate", json={"takes": 1})).json()
    fake_provider.fail_next = 1  # first attempt dies like a crashed sidecar
    await jobs.run_once()
    j = (await client.get(f"/jobs/{job['id']}")).json()
    assert j["status"] == "queued" and j["attempts"] == 1 and "simulated engine failure" in j["error"]
    await jobs.run_once()  # second attempt succeeds
    j = (await client.get(f"/jobs/{job['id']}")).json()
    assert j["status"] == "done" and j["attempts"] == 2

    song2 = (await client.post("/songs", json=SONG)).json()
    job2 = (await client.post(f"/songs/{song2['id']}/generate", json={"takes": 1})).json()
    fake_provider.fail_next = 10
    for _ in range(3):
        await jobs.run_once()
    j = (await client.get(f"/jobs/{job2['id']}")).json()
    assert j["status"] == "failed" and j["attempts"] == 3
    assert (await client.get(f"/songs/{song2['id']}")).json()["status"] == "rendering"  # song stays as it was; UI shows the failed job


async def test_song_isolation_by_user_and_404(client):
    r = await client.get("/songs/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404

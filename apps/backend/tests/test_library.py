"""Library: search/filter/kept, delete song removes files, delete one take."""
from __future__ import annotations

from app.services import jobs
from app.services.storage import get_storage

POP = {"title": "Run With Me", "style": "modern pop, synth bass", "lyrics": "[Verse]\nneon city", "bpm": 118, "duration_s": 30}
FOLK = {"title": "Gravel Road", "style": "acoustic folk, harmonica", "lyrics": "[Verse]\nporch light", "bpm": 92, "duration_s": 30}


async def _rendered(client, body):
    song = (await client.post("/songs", json=body)).json()
    await client.post(f"/songs/{song['id']}/generate", json={"takes": 2})
    await jobs.run_once()
    return (await client.get(f"/songs/{song['id']}")).json()


async def test_search_filter_and_kept(client):
    pop = await _rendered(client, POP)
    folk = (await client.post("/songs", json=FOLK)).json()  # stays a draft
    assert {s["title"] for s in (await client.get("/songs")).json()} == {"Run With Me", "Gravel Road"}
    assert [s["title"] for s in (await client.get("/songs?q=neon")).json()] == ["Run With Me"]      # lyrics
    assert [s["title"] for s in (await client.get("/songs?q=harmonica")).json()] == ["Gravel Road"]  # style
    assert [s["title"] for s in (await client.get("/songs?q=GRAVEL")).json()] == ["Gravel Road"]     # case-insensitive title
    assert [s["title"] for s in (await client.get("/songs?status=ready")).json()] == ["Run With Me"]
    assert (await client.get("/songs?kept=true")).json() == []
    r = await client.post(f"/generations/{pop['generations'][0]['id']}/favorite")
    assert r.json()["is_favorite"] is True
    assert [s["title"] for s in (await client.get("/songs?kept=true")).json()] == ["Run With Me"]


async def test_delete_song_removes_rows_and_files(client):
    pop = await _rendered(client, POP)
    folder = get_storage().root / "generations" / pop["id"]
    assert folder.exists() and any(folder.rglob("*.wav"))
    r = await client.delete(f"/songs/{pop['id']}")
    assert r.status_code == 204
    assert (await client.get(f"/songs/{pop['id']}")).status_code == 404
    assert (await client.get(f"/generations/{pop['generations'][0]['id']}/audio")).status_code == 404
    assert not folder.exists()
    assert (await client.delete(f"/songs/{pop['id']}")).status_code == 404


async def test_delete_one_take(client):
    pop = await _rendered(client, POP)
    g0, g1 = pop["generations"]
    r = await client.delete(f"/generations/{g0['id']}")
    assert r.status_code == 204
    s = (await client.get(f"/songs/{pop['id']}")).json()
    assert [g["id"] for g in s["generations"]] == [g1["id"]]
    assert (await client.get(f"/generations/{g0['id']}/audio")).status_code == 404
    assert (await client.get(f"/generations/{g1['id']}/audio")).status_code == 200

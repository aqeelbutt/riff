"""Probe: understand the user's song (transcript + key/tempo) with Claude, then have the engine PERFORM it fresh in two
directions with the same words. Writes MP3s to spike/out/share/reimagine/. Run from apps/backend with the real .env."""
import asyncio, json, sys, time
from pathlib import Path
sys.path.insert(0, ".")
from app.services.ai.lyrics import ReimagineInput, get_lyrics_provider
from app.services.music import RenderRequest, CoverRequest, get_provider
from app.services.mastering import master

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "spike/out/share/reimagine"; OUT.mkdir(parents=True, exist_ok=True)
LYRICS = (ROOT / "spike/out/aqeel-test-1.lyrics.txt").read_text()
DIRECTIONS = {
    "ballad": ("emotional ballad", "emotional Urdu pop ballad, intimate piano and warm strings, soft brushed drums entering on the second verse, swelling cello and choir pads into the chorus, tender then soaring male vocal, cinematic dynamics, wide reverb"),
    "anthem": ("cinematic anthem", "cinematic sufi-pop anthem, harmonium and tabla under lush orchestral strings, big rolling drums building to a euphoric chorus with stacked harmonies, powerful passionate male vocal, dramatic lifts, epic and hopeful"),
}

async def main():
    lp, mp = get_lyrics_provider(), get_provider()
    print("lyrics provider:", lp.name, "· engine:", mp.name)
    for key, (direction, cap) in DIRECTIONS.items():
        t0 = time.time()
        b = await lp.reimagine(ReimagineInput(lyrics=LYRICS, key="G minor", bpm=126, vocal_language="ur", direction=direction, direction_caption=cap, vocal="male", duration_s=180))
        print(f"\n=== {key} · brief in {time.time()-t0:.0f}s\n title: {b.title}\n meaning: {b.meaning}\n key {b.key} · {b.bpm} BPM · {b.vocal}\n arc: {b.arc}\n caption: {b.style_caption[:220]}\n structure: {b.structure}\n lyrics:\n{b.lyrics[:700]}")
        (OUT / f"{key}.brief.json").write_text(json.dumps(b.model_dump(), ensure_ascii=False, indent=1))
        t0 = time.time()
        res = await mp.render(RenderRequest(style=b.style_caption, lyrics=b.lyrics, duration_s=180, bpm=b.bpm, key=b.key, vocal_language="ur", takes=2, out_dir=OUT / key))
        print(f" rendered {len(res.takes)} takes in {res.render_seconds}s")
        for i, tk in enumerate(res.takes, 1):
            wav, mp3, lufs = await master(tk.path)
            dst = OUT / f"aqeel-reimagined-{key}-{i}.mp3"; mp3.replace(dst); print("  ", dst.name, "lufs", lufs, "seed", tk.seed)
    # plus: a LOOSE cover (strength 0.3) in the ballad direction — keeps a memory of the original melody
    b = json.loads((OUT / "ballad.brief.json").read_text())
    res = await mp.cover(CoverRequest(src_path=ROOT / "spike/in/aqeel-test-1.wav", style=b["style_caption"], lyrics=b["lyrics"], strength=0.3, bpm=b["bpm"], vocal_language="ur", out_dir=OUT / "cover"))
    wav, mp3, lufs = await master(res.takes[0].path); mp3.replace(OUT / "aqeel-reimagined-ballad-loosecover.mp3"); print(" loose cover", res.render_seconds, "s lufs", lufs)

asyncio.run(main())

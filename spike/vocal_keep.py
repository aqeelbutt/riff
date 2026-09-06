#!/usr/bin/env python3
"""Vocal-keep remix: keep the user's REAL vocal, regenerate the instrumental bed in a new style.

Pipeline (the plan's "Vocal-keep" mode, proven here on a real upload):
  stems (Demucs)  →  instrumental = drums+bass+other  →  [optional tempo stretch of BOTH vocal + instrumental]
  →  ACE-Step COVER of the instrumental (no lyrics ⇒ instrumental output)  →  mix vocal over the new bed
  →  loudness-normalize to -14 LUFS  →  WAV + MP3

usage:
  vocal_keep.py --stems spike/out/stems-user/norm --name aqeel-emo-house --caption "..." --bpm-from 126 --bpm-to 126 --strength 0.5
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time, urllib.request
from pathlib import Path
import numpy as np, soundfile as sf, pyloudnorm as pyln
try:
    import pyrubberband as pyrb
except ImportError:
    pyrb = None

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "spike/out"
SPIKE = ROOT / "spike/run_spike.py"

def stretch(y, sr, ratio):
    if abs(ratio - 1) < 1e-3: return y
    if pyrb is None: sys.exit("pyrubberband missing")
    return pyrb.time_stretch(y, sr, ratio)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stems", required=True); ap.add_argument("--name", required=True); ap.add_argument("--caption", required=True)
    ap.add_argument("--bpm-from", type=float, required=True); ap.add_argument("--bpm-to", type=float, required=True)
    ap.add_argument("--strength", type=float, default=0.5); ap.add_argument("--vocal-db", type=float, default=0.0, help="vocal gain vs bed")
    ap.add_argument("--lang", default="en")
    a = ap.parse_args()
    t0 = time.time()
    stems = Path(a.stems)
    voc, sr = sf.read(stems / "vocals.wav"); inst, _ = sf.read(stems / "instrumental.wav")
    ratio = a.bpm_to / a.bpm_from   # rubberband rate: >1 = faster/shorter
    if abs(ratio - 1) > 1e-3:
        print(f"stretching vocal + instrumental ×{ratio:.3f} ({a.bpm_from:.0f} → {a.bpm_to:.0f} BPM)")
        voc = stretch(voc, sr, ratio); inst = stretch(inst, sr, ratio)
    work = OUT / "vk"; work.mkdir(exist_ok=True)
    inst_path = work / f"{a.name}.inst.wav"; sf.write(inst_path, inst, sr, subtype="PCM_16")
    # cover the instrumental only — no lyrics ⇒ the engine renders an instrumental bed
    print("rendering new bed via cover…")
    r = subprocess.run([sys.executable, str(SPIKE), "cover", "--name", f"{a.name}-bed", "--src", str(inst_path), "--caption", a.caption,
                        "--strength", str(a.strength), "--steps", "8", "--shift", "3", "--model", "acestep-v15-turbo", "--bpm", str(int(a.bpm_to))],
                       capture_output=True, text=True)
    print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-800:])
    bed_path = OUT / f"{a.name}-bed_1.wav"
    if not bed_path.exists(): sys.exit("bed render failed")
    bed, bsr = sf.read(bed_path)
    if bsr != sr:  # resample bed to the vocal's rate
        import librosa; bed = librosa.resample(bed.T, orig_sr=bsr, target_sr=sr).T
    n = min(len(bed), len(voc)); bed = bed[:n]; voc = voc[:n]
    if voc.ndim == 1: voc = np.stack([voc, voc], 1)
    if bed.ndim == 1: bed = np.stack([bed, bed], 1)
    # balance: bring the bed to the vocal's loudness neighbourhood, then add vocal with its offset
    m = pyln.Meter(sr)
    lb, lv = m.integrated_loudness(bed), m.integrated_loudness(voc)
    bed_gain = 10 ** ((lv - 4 - lb) / 20)   # bed sits ~4 LU under the vocal before mix
    mix = bed * bed_gain + voc * 10 ** (a.vocal_db / 20)
    mix = pyln.normalize.loudness(mix, m.integrated_loudness(mix), -14.0)
    peak = np.abs(mix).max();  mix = mix / peak * 0.98 if peak > 0.98 else mix
    out_wav = OUT / f"{a.name}.wav"; sf.write(out_wav, mix, sr, subtype="PCM_16")
    out_mp3 = OUT / "share/remix" / f"{a.name}.mp3"; out_mp3.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out_wav), "-codec:a", "libmp3lame", "-q:a", "2", str(out_mp3)], check=True)
    el = round(time.time() - t0, 1)
    with open(OUT / "results.jsonl", "a") as f:
        f.write(json.dumps({"name": a.name, "task": "vocal_keep", "elapsed_s": el, "bpm_from": a.bpm_from, "bpm_to": a.bpm_to, "strength": a.strength, "outputs": [str(out_wav), str(out_mp3)]}) + "\n")
    print(f"✓ {a.name}: {el}s → {out_mp3}  (bed LUFS {lb:.1f}, vocal LUFS {lv:.1f}, mix → -14)")

if __name__ == "__main__":
    main()

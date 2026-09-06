#!/usr/bin/env python3
"""Vocal transformation layer on a REAL vocal stem: harmonies, doubles, delay throws, intro chops.
Mixes the treated vocal over a bed (or over an already-mixed track). Pure DSP, CPU only.

usage: vocal_fx.py --vocal stems/vocals.wav --bed bed.wav --bpm 126 --name out-name [--harmony 7,12] [--chops]
"""
import argparse, subprocess, sys, time
from pathlib import Path
import numpy as np, soundfile as sf, pyloudnorm as pyln, pyrubberband as pyrb

OUT = Path(__file__).resolve().parent.parent / "spike/out"

def db(x): return 10 ** (x / 20)
def pan(mono, p):  # p in [-1,1]
    l = mono * np.cos((p + 1) * np.pi / 4); r = mono * np.sin((p + 1) * np.pi / 4); return np.stack([l, r], 1)
def delay_taps(x, sr, beat, taps=(1, 2, 3), gains=(-10, -15, -20), div=0.5):
    y = np.zeros_like(x); step = int(beat * div * sr)
    for t, g in zip(taps, gains):
        d = step * t
        if d < len(x): y[d:] += x[:-d] * db(g)
    return y

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vocal", required=True); ap.add_argument("--bed", required=True); ap.add_argument("--bpm", type=float, required=True)
    ap.add_argument("--name", required=True); ap.add_argument("--harmony", default="7,12"); ap.add_argument("--chops", action="store_true")
    ap.add_argument("--vocal-db", type=float, default=0.0); ap.add_argument("--bed-under", type=float, default=3.0, help="LU the bed sits under the lead")
    a = ap.parse_args(); t0 = time.time()
    voc, sr = sf.read(a.vocal); bed, bsr = sf.read(a.bed)
    if bsr != sr:
        import librosa; bed = librosa.resample(bed.T, orig_sr=bsr, target_sr=sr).T
    if voc.ndim == 2: vm = voc.mean(1)
    else: vm = voc
    n = min(len(vm), len(bed)); vm = vm[:n]; bed = bed[:n]
    beat = 60 / a.bpm
    lead = pan(vm, 0)
    layers = [lead * db(a.vocal_db)]
    # doubles: two slightly detuned/delayed copies panned wide (thickens the lead)
    for cents, ms, p in ((-8, 18, -0.7), (+8, 24, 0.7)):
        d = pyrb.pitch_shift(vm, sr, cents / 100); off = int(ms / 1000 * sr)
        d = np.concatenate([np.zeros(off), d[:-off]]) if off else d
        layers.append(pan(d, p) * db(-9))
    # harmonies: pitch-shifted copies (default a fifth up + an octave up), quieter, wide
    for i, semis in enumerate(int(s) for s in a.harmony.split(",") if s):
        h = pyrb.pitch_shift(vm, sr, semis); layers.append(pan(h, -0.5 if i % 2 == 0 else 0.5) * db(-11 - 2 * i))
    # delay throws on the lead: dotted-eighth feedback echoes, low-passed feel by the level drop
    layers.append(pan(delay_taps(vm, sr, beat, div=0.75), 0.3) * db(-6))
    # chops: stutter the first strong phrase over the intro (bar 1-2), eighth-note gate
    if a.chops:
        env = np.convolve(np.abs(vm), np.ones(int(0.05 * sr)) / (0.05 * sr), "same")
        start = int(np.argmax(env > env.max() * 0.35)); phrase = vm[start:start + int(beat * 2)]
        slice_len = int(beat / 2 * sr); piece = phrase[:slice_len] * np.hanning(min(slice_len, len(phrase)))[:len(phrase[:slice_len])]
        chop = np.zeros(n); pos = 0
        for k in range(16):  # 2 bars of eighth-note stutters, alternating pitch
            seg = pyrb.pitch_shift(piece, sr, 0 if k % 4 else 5) if k % 4 == 0 else piece
            end = min(pos + len(seg), n); chop[pos:end] += seg[:end - pos]; pos += slice_len
        layers.append(pan(chop, 0) * db(-4))
    vox = sum(layers)
    m = pyln.Meter(sr); lv = m.integrated_loudness(vox); lb = m.integrated_loudness(bed)
    mix = bed * db(lv - a.bed_under - lb) + vox
    mix = pyln.normalize.loudness(mix, m.integrated_loudness(mix), -14.0)
    pk = np.abs(mix).max(); mix = mix / pk * 0.98 if pk > 0.98 else mix
    wav = OUT / f"{a.name}.wav"; sf.write(wav, mix, sr, subtype="PCM_16")
    mp3 = OUT / "share/remix" / f"{a.name}.mp3"; mp3.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-codec:a", "libmp3lame", "-q:a", "2", str(mp3)], check=True)
    print(f"✓ {a.name}: {time.time()-t0:.0f}s → {mp3}  layers={len(layers)} harmony={a.harmony} chops={a.chops}")

if __name__ == "__main__":
    main()

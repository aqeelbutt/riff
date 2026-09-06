#!/usr/bin/env python3
"""Vocal treatment + mix. The user's REAL vocal is the lead: auto-tuned (formant-preserving, per-note, blended), placed
clean and in front. Under it: a bed (instrumental) and, for hybrid, the AI cover's vocals DUCKED by the lead's envelope so
they answer in the gaps instead of colliding. Optional doubles/harmonies/chops are OFF by default. Everything can be
stretched together to `bpm_to` (after the cover, never before). Output −14 LUFS. JSON on stdout.

usage: vocal_mix.py '{"vocal": "...wav" | null, "bed": "...wav", "ai_vocals": "...wav" | null, "out": "...wav",
  "bpm": 126, "key": "G major", "bpm_to": 0, "autotune": true, "autotune_strength": 0.85,
  "harmony": "", "doubles": false, "chops": false, "ai_level_db": -6, "ai_duck_db": 12, "bed_under": 2, "vocal_db": 0}'
"""
import json
import sys
import warnings

warnings.filterwarnings("ignore")
import numpy as np  # noqa: E402
import pyloudnorm as pyln  # noqa: E402
import soundfile as sf  # noqa: E402

try:
    import pyrubberband as pyrb
except ImportError:  # pragma: no cover
    pyrb = None

KEYS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#", "D♭": "C#", "E♭": "D#", "G♭": "F#", "A♭": "G#", "B♭": "A#"}
MAJOR_STEPS, MINOR_STEPS = [0, 2, 4, 5, 7, 9, 11], [0, 2, 3, 5, 7, 8, 10]


def db(x): return 10 ** (x / 20)
def mono(a): return a.mean(1) if a.ndim == 2 else a
def pan(m, p): return np.stack([m * np.cos((p + 1) * np.pi / 4), m * np.sin((p + 1) * np.pi / 4)], 1)


def scale_pcs(key: str):
    """'F# minor' → pitch classes in the scale; unknown → chromatic."""
    try:
        tonic, mode = key.replace("♯", "#").split()
        root = KEYS.index(FLAT.get(tonic, tonic))
        return {(root + s) % 12 for s in (MINOR_STEPS if mode.lower().startswith("min") else MAJOR_STEPS)}
    except Exception:  # noqa: BLE001
        return set(range(12))


def pitch_shift(x, sr, semis):
    """Formant-preserving, high-quality shift via Rubber Band; librosa as a fallback."""
    if pyrb is not None:
        try:
            return pyrb.pitch_shift(x, sr, semis, rbargs={"--formant": "", "--pitch-hq": ""})
        except Exception:  # noqa: BLE001
            return pyrb.pitch_shift(x, sr, semis)
    import librosa
    return librosa.effects.pitch_shift(x, sr=sr, n_steps=float(semis))


def autotune(vm, sr, key: str, strength: float):
    """Per-note correction: pyin → note regions (stable pitch ≥ 80 ms) → nearest scale tone → shift by strength·offset with
    crossfades. Only the LEAD is corrected; nothing is layered on top of it here."""
    import librosa
    hop = 512
    f0, voiced, _ = librosa.pyin(vm, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C6"), sr=sr, hop_length=hop)
    midi = librosa.hz_to_midi(np.where(np.isnan(f0), 0, f0))
    allowed = scale_pcs(key)
    out = np.copy(vm); n = len(vm)
    i, frames, notes = 0, len(midi), 0
    while i < frames:
        if not voiced[i] or midi[i] <= 0:
            i += 1; continue
        j = i + 1; seg = [midi[i]]
        while j < frames and voiced[j] and midi[j] > 0 and abs(midi[j] - float(np.median(seg))) < 0.6:
            seg.append(midi[j]); j += 1
        if (j - i) * hop >= int(0.08 * sr):
            m = float(np.median(seg)); base = int(round(m))
            cands = [base + d for d in range(-6, 7) if (base + d) % 12 in allowed]
            target = min(cands, key=lambda c: abs(c - m)) if cands else base
            shift = (target - m) * strength
            if abs(shift) > 0.03:
                pad = int(0.025 * sr); a0, b0 = max(0, i * hop - pad), min(n, j * hop + pad)
                chunk = vm[a0:b0]
                if len(chunk) > 4096:
                    sh = pitch_shift(chunk, sr, float(shift)); L = min(len(sh), b0 - a0)
                    w = np.ones(L); fade = min(pad, L // 4)
                    if fade > 0:
                        w[:fade] = np.linspace(0, 1, fade); w[-fade:] = np.linspace(1, 0, fade)
                    out[a0:a0 + L] = out[a0:a0 + L] * (1 - w) + sh[:L] * w
                    notes += 1
        i = max(j, i + 1)
    return out, notes


def envelope(x, sr, attack_ms=5, release_ms=250):
    """Peak-follower envelope (fast attack, slow release) used to duck the AI vocals under the lead."""
    a = np.exp(-1 / (sr * attack_ms / 1000)); r = np.exp(-1 / (sr * release_ms / 1000))
    env = np.zeros_like(x); e = 0.0
    ax = np.abs(x)
    for k in range(len(ax)):
        v = ax[k]
        e = v + (e - v) * (a if v > e else r)
        env[k] = e
    return env


def duck(target, lead_env, sr, depth_db=12.0, thresh=0.02):
    """Gain-reduce `target` where the lead is active: up to depth_db down, proportional to lead level above thresh."""
    g = np.clip((lead_env - thresh) / (0.2 - thresh), 0, 1)  # 0..1 how loud the lead is
    gain = db(-depth_db * g)
    return target * gain[:, None] if target.ndim == 2 else target * gain


def delay_taps(x, sr, beat, div=0.75, taps=(1, 2), gains=(-14, -20)):
    y = np.zeros_like(x); step = int(beat * div * sr)
    for t, g in zip(taps, gains):
        d = step * t
        if 0 < d < len(x): y[d:] += x[:-d] * db(g)
    return y


def main(cfg: dict) -> None:
    bed, sr = sf.read(cfg["bed"])
    if bed.ndim == 1: bed = np.stack([bed, bed], 1)
    m = pyln.Meter(sr)
    ratio = (cfg.get("bpm_to") or 0) / cfg["bpm"] if cfg.get("bpm_to") else 1.0
    info = {"notes_tuned": 0}
    beat = 60 / float(cfg["bpm"])
    lead = None; ai = None
    if cfg.get("vocal"):
        voc, vsr = sf.read(cfg["vocal"])
        if vsr != sr:
            import librosa; voc = librosa.resample(voc.T, orig_sr=vsr, target_sr=sr).T
        vm = mono(voc)
        n = min(len(vm), len(bed)); vm = vm[:n]; bed = bed[:n]
        if cfg.get("autotune", True) and float(cfg.get("autotune_strength", 0.85)) > 0:
            vm, info["notes_tuned"] = autotune(vm, sr, cfg.get("key") or "", float(cfg.get("autotune_strength", 0.85)))
        layers = [pan(vm, 0) * db(float(cfg.get("vocal_db", 0)))]
        if cfg.get("doubles"):
            for cents, ms, p in ((-8, 18, -0.7), (8, 24, 0.7)):
                d = pitch_shift(vm, sr, cents / 100); off = int(ms / 1000 * sr)
                layers.append(pan(np.concatenate([np.zeros(off), d[:-off]]) if off else d, p) * db(-12))
        for i, semis in enumerate(int(x) for x in str(cfg.get("harmony") or "").split(",") if x.strip()):
            layers.append(pan(pitch_shift(vm, sr, semis), -0.5 if i % 2 == 0 else 0.5) * db(-13 - 2 * i))
        layers.append(pan(delay_taps(vm, sr, beat), 0.3) * db(-4))
        if cfg.get("chops"):
            env = np.convolve(np.abs(vm), np.ones(int(0.05 * sr)) / (0.05 * sr), "same")
            start = int(np.argmax(env > env.max() * 0.35)); phrase = vm[start:start + int(beat * 2)]
            sl = int(beat / 2 * sr); piece = phrase[:sl] * np.hanning(min(sl, len(phrase)))[:len(phrase[:sl])]
            chop = np.zeros(n); pos = 0
            for k in range(16):
                seg = pitch_shift(piece, sr, 5) if k % 4 == 0 else piece
                end = min(pos + len(seg), n); chop[pos:end] += seg[:end - pos]; pos += sl
            layers.append(pan(chop, 0) * db(-6))
        lead = sum(layers)
        if cfg.get("ai_vocals"):
            av, asr = sf.read(cfg["ai_vocals"])
            if asr != sr:
                import librosa; av = librosa.resample(av.T, orig_sr=asr, target_sr=sr).T
            if av.ndim == 1: av = np.stack([av, av], 1)
            av = av[:n]
            if len(av) < n: av = np.vstack([av, np.zeros((n - len(av), 2))])
            ai = duck(av, envelope(vm, sr), sr, depth_db=float(cfg.get("ai_duck_db", 12)))
    # tempo: stretch everything together
    parts = {"bed": bed, "lead": lead, "ai": ai}
    if abs(ratio - 1) > 1e-3 and pyrb is not None:
        for k, v in parts.items():
            if v is not None: parts[k] = pyrb.time_stretch(v, sr, ratio)
        L = min(len(v) for v in parts.values() if v is not None); parts = {k: (v[:L] if v is not None else None) for k, v in parts.items()}
    bed, lead, ai = parts["bed"], parts["lead"], parts["ai"]
    if lead is not None:
        lv = m.integrated_loudness(lead); lb = m.integrated_loudness(bed)
        mix = bed * db(lv - float(cfg.get("bed_under", 2.0)) - lb) + lead
        if ai is not None:
            la = m.integrated_loudness(ai) if np.abs(ai).max() > 1e-4 else lv
            mix = mix + ai * db(lv + float(cfg.get("ai_level_db", -6)) - la)
    else:
        mix = bed
    mix = pyln.normalize.loudness(mix, m.integrated_loudness(mix), -14.0)
    pk = float(np.abs(mix).max()); mix = mix / pk * 0.98 if pk > 0.98 else mix
    sf.write(cfg["out"], mix, sr, subtype="PCM_16")
    print(json.dumps({"out": cfg["out"], "lufs": round(float(m.integrated_loudness(mix)), 1), "duration_s": round(len(mix) / sr, 2), **info}))


if __name__ == "__main__":
    main(json.loads(sys.argv[1]))

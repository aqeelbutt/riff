#!/usr/bin/env python3
"""Demucs stems (reference implementation, MPS) → vocals/drums/bass/other + instrumental WAVs in out_dir; JSON on stdout.
usage: separate.py <src.wav> <out_dir> [model]"""
import json
import subprocess
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402


def main(src: str, out_dir: str, model: str = "htdemucs_ft") -> None:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    work = out / "_demucs"
    r = subprocess.run([sys.executable, "-m", "demucs", "-n", model, "-d", "mps", "-o", str(work), "--float32", src], capture_output=True, text=True)
    if r.returncode != 0:
        # MPS can fail on exotic hosts — fall back to CPU once
        r = subprocess.run([sys.executable, "-m", "demucs", "-n", model, "-d", "cpu", "-o", str(work), "--float32", src], capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr[-1500:], file=sys.stderr); sys.exit(1)
    d = work / model / Path(src).stem
    stems = {k: sf.read(d / f"{k}.wav") for k in ("vocals", "drums", "bass", "other")}
    sr = stems["vocals"][1]
    tot = sum(float(np.mean(a**2)) for a, _ in stems.values()) or 1.0
    result = {"sr": sr, "stems": {}}
    for k, (a, _) in stems.items():
        p = out / f"{k}.wav"; sf.write(p, a, sr, subtype="FLOAT")
        result["stems"][k] = {"path": str(p), "energy_share": round(float(np.mean(a**2)) / tot, 4)}
    inst = np.clip(stems["drums"][0] + stems["bass"][0] + stems["other"][0], -1, 1)
    p = out / "instrumental.wav"; sf.write(p, inst, sr, subtype="FLOAT")
    result["stems"]["instrumental"] = {"path": str(p), "energy_share": None}
    print(json.dumps(result))


if __name__ == "__main__":
    main(*sys.argv[1:])

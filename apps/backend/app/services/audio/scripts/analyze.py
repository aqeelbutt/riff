#!/usr/bin/env python3
"""Tempo, key, loudness, duration of one audio file → JSON on stdout. Runs in the tools venv."""
import json
import sys
import warnings

warnings.filterwarnings("ignore")
import librosa  # noqa: E402
import numpy as np  # noqa: E402
import pyloudnorm as pyln  # noqa: E402

KEYS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def key_of(chroma):
    best = (-1, "C major")
    for i in range(12):
        for name, prof in (("major", MAJOR), ("minor", MINOR)):
            c = float(np.corrcoef(np.roll(prof, i), chroma)[0, 1])
            if c > best[0]:
                best = (c, f"{KEYS[i]} {name}")
    return best[1]


def main(path: str) -> None:
    y, sr = librosa.load(path, sr=None, mono=True)
    tempo = float(np.atleast_1d(librosa.beat.beat_track(y=y, sr=sr)[0])[0])
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr).mean(axis=1)
    lufs = float(pyln.Meter(sr).integrated_loudness(y))
    print(json.dumps({"duration_s": round(len(y) / sr, 2), "bpm": round(tempo, 1), "key": key_of(chroma), "lufs": round(lufs, 1), "sr": sr}))


if __name__ == "__main__":
    main(sys.argv[1])

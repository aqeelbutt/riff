#!/usr/bin/env bash
# One GPU lane: transcribe (Whisper) → build stems dir → vocal-keep renders. usage: run_vocal_keep_user.sh <demucs_dir> <base> <lang> <src_bpm>
set -uo pipefail; cd "$(dirname "${BASH_SOURCE[0]}")/.."
D="$1"; B="$2"; LANG_CODE="$3"; BPM="$4"; PY=services/stems/.venv/bin/python
echo "### vocal-keep start $(date)"
$PY spike/transcribe.py "$D/vocals.wav" "$LANG_CODE" "spike/out/$B.lyrics" 2>&1 | grep -vE "%\|" | tail -1
mkdir -p "spike/out/stems-$B" && $PY - "$D" "spike/out/stems-$B" <<'PY'
import sys, numpy as np, soundfile as sf
d,o=sys.argv[1],sys.argv[2]
v,sr=sf.read(d+"/vocals.wav"); inst=sum(sf.read(d+"/"+k+".wav")[0] for k in ["drums","bass","other"])
sf.write(o+"/vocals.wav",v,sr,subtype="FLOAT"); sf.write(o+"/instrumental.wav",np.clip(inst,-1,1),sr,subtype="FLOAT"); print("stems dir ready", o)
PY
curl -sf http://127.0.0.1:8001/health >/dev/null || { scripts/engine.sh start; for i in $(seq 1 40); do curl -sf http://127.0.0.1:8001/health >/dev/null && break; sleep 5; done; }
EMO="emotional melodic deep house, 118 BPM, chill and dreamy, lush warm analog pads, gentle piano melody lines and soft synth arpeggios, deep rolling sub bass, soft four-on-the-floor kick with sidechain, airy hi-hats, wide reverb, late-night cinematic feel, instrumental"
CHILL="chill downtempo deep house, 108 BPM, very relaxed and emotional, soft lo-fi drums, warm Rhodes and piano melodies, floating pads, subtle strings, deep sub bass, intimate and dreamy, instrumental"
$PY spike/vocal_keep.py --stems "spike/out/stems-$B" --name "$B-vk-emo-118" --caption "$EMO" --bpm-from "$BPM" --bpm-to 118 --strength 0.5 --lang "$LANG_CODE"
$PY spike/vocal_keep.py --stems "spike/out/stems-$B" --name "$B-vk-chill-108" --caption "$CHILL" --bpm-from "$BPM" --bpm-to 108 --strength 0.5 --lang "$LANG_CODE"
$PY spike/vocal_keep.py --stems "spike/out/stems-$B" --name "$B-vk-emo-126" --caption "$EMO" --bpm-from "$BPM" --bpm-to "$BPM" --strength 0.5 --lang "$LANG_CODE"
echo "### vocal-keep done $(date)"

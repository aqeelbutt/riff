#!/usr/bin/env bash
# Phase 0 timing + quality matrix. Runs sequentially against the sidecar on :8001.
# Results accumulate in spike/out/results.jsonl; audio in spike/out/*.wav.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
R="python3 spike/run_spike.py"

POP="upbeat modern pop anthem, driving synth bass, bright electric guitars, punchy drums, female lead vocal, catchy singalong chorus, 118 BPM, polished radio production"
HIPHOP="modern hip-hop, trap-influenced, heavy 808 bass, crisp hi-hats, dark piano motif, confident male rap vocal, 140 BPM half-time feel"
FOLK="warm acoustic folk-country, fingerpicked acoustic guitar, brushed drums, upright bass, harmonica touches, intimate male vocal with harmonies, 92 BPM"
DEEPHOUSE="deep house remix, 124 BPM, four-on-the-floor kick, sidechained warm pads, filtered chord stabs, rolling sub bass, shuffled hi-hats, late-night club atmosphere, keep the vocals"

echo "### matrix start $(date)"

# 1. Three genres, turbo defaults (8 steps, shift 3), no LM planning, one take each, 150 s
$R text2music --name pop-turbo    --lyrics spike/lyrics/pop.txt    --caption "$POP"    --duration 150 --steps 8 --shift 3 --model acestep-v15-turbo --seed 1001
$R text2music --name hiphop-turbo --lyrics spike/lyrics/hiphop.txt --caption "$HIPHOP" --duration 150 --steps 8 --shift 3 --model acestep-v15-turbo --seed 1002
$R text2music --name folk-turbo   --lyrics spike/lyrics/folk.txt   --caption "$FOLK"   --duration 150 --steps 8 --shift 3 --model acestep-v15-turbo --seed 1003

# 2. Same pop song with LM planning on (thinking=true) — quality/time delta
$R text2music --name pop-turbo-think --lyrics spike/lyrics/pop.txt --caption "$POP" --duration 150 --steps 8 --shift 3 --model acestep-v15-turbo --thinking --seed 1001

# 3. Product default: 2 variations in one batch
$R text2music --name pop-turbo-batch2 --lyrics spike/lyrics/pop.txt --caption "$POP" --duration 150 --steps 8 --shift 3 --model acestep-v15-turbo --batch 2

# 4. SFT (50 steps, CFG) — the "higher quality, slower" toggle
$R text2music --name pop-sft --lyrics spike/lyrics/pop.txt --caption "$POP" --duration 150 --steps 50 --model acestep-v15-sft --seed 1001

# 5. Covers → deep house (turbo). Two strengths on pop, one on folk.
$R cover --name pop-to-deephouse-045  --src spike/out/pop-turbo_1.wav  --lyrics spike/lyrics/pop.txt  --caption "$DEEPHOUSE" --strength 0.45 --steps 8 --shift 3 --model acestep-v15-turbo --bpm 124
$R cover --name pop-to-deephouse-065  --src spike/out/pop-turbo_1.wav  --lyrics spike/lyrics/pop.txt  --caption "$DEEPHOUSE" --strength 0.65 --steps 8 --shift 3 --model acestep-v15-turbo --bpm 124
$R cover --name folk-to-deephouse-045 --src spike/out/folk-turbo_1.wav --lyrics spike/lyrics/folk.txt --caption "$DEEPHOUSE" --strength 0.45 --steps 8 --shift 3 --model acestep-v15-turbo --bpm 124

# 6. Stems on the pop take (htdemucs_ft via MLX)
S=services/stems/.venv/bin/mlx-audio-separator
t0=$(date +%s)
$S -m htdemucs_ft.yaml --model_file_dir services/stems/models --output_dir spike/out/stems --output_format WAV spike/out/pop-turbo_1.wav 2>&1 | grep -iE "separat|saved|error|complete" | tail -6
echo "{\"name\": \"stems-pop-htdemucs_ft\", \"elapsed_s\": $(( $(date +%s) - t0 )), \"task\": \"stems\"}" >> spike/out/results.jsonl
ls -la spike/out/stems 2>/dev/null

echo "### matrix done $(date)"

#!/usr/bin/env bash
# Phase 0 timing + quality matrix. Runs sequentially against the sidecar on :8001.
# Idempotent: a run whose first output already exists is skipped, so a crash
# mid-matrix can be resumed by re-running the script.
# Results accumulate in spike/out/results.jsonl; audio in spike/out/*.wav.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

POP="upbeat modern pop anthem, driving synth bass, bright electric guitars, punchy drums, female lead vocal, catchy singalong chorus, 118 BPM, polished radio production"
HIPHOP="modern hip-hop, trap-influenced, heavy 808 bass, crisp hi-hats, dark piano motif, confident male rap vocal, 140 BPM half-time feel"
FOLK="warm acoustic folk-country, fingerpicked acoustic guitar, brushed drums, upright bass, harmonica touches, intimate male vocal with harmonies, 92 BPM"
DEEPHOUSE="deep house remix, 124 BPM, four-on-the-floor kick, sidechained warm pads, filtered chord stabs, rolling sub bass, shuffled hi-hats, late-night club atmosphere, keep the vocals"

run() {  # run <name> <args...>
  local name="$1"; shift
  if [[ -f "spike/out/${name}_1.wav" ]]; then echo "skip $name (exists)"; return 0; fi
  python3 spike/run_spike.py "$@" --name "$name" 2>&1 | tr '\r' '\n' | grep -vE "^\s*… "
  if ! curl -sf http://127.0.0.1:8001/health >/dev/null; then
    echo "!!! engine is down after $name — restart it (scripts/engine.sh start) and re-run this script"; exit 1
  fi
}

echo "### matrix start $(date)"

# 1. Three genres, turbo defaults (8 steps, shift 3), no LM planning, one take each, 150 s
run pop-turbo    text2music --lyrics spike/lyrics/pop.txt    --caption "$POP"    --duration 150 --steps 8 --shift 3 --model acestep-v15-turbo --seed 1001
run hiphop-turbo text2music --lyrics spike/lyrics/hiphop.txt --caption "$HIPHOP" --duration 150 --steps 8 --shift 3 --model acestep-v15-turbo --seed 1002
run folk-turbo   text2music --lyrics spike/lyrics/folk.txt   --caption "$FOLK"   --duration 150 --steps 8 --shift 3 --model acestep-v15-turbo --seed 1003

# 2. Same pop song with the 5Hz LM planning codes (thinking=true) — quality/time delta
run pop-turbo-think text2music --lyrics spike/lyrics/pop.txt --caption "$POP" --duration 150 --steps 8 --shift 3 --model acestep-v15-turbo --thinking --seed 1001

# 3. Product default: 2 variations in one batch
run pop-turbo-batch2 text2music --lyrics spike/lyrics/pop.txt --caption "$POP" --duration 150 --steps 8 --shift 3 --model acestep-v15-turbo --batch 2

# 4. SFT (50 steps, CFG) — the "higher quality, slower" toggle
run pop-sft text2music --lyrics spike/lyrics/pop.txt --caption "$POP" --duration 150 --steps 50 --model acestep-v15-sft --seed 1001

# 5. Covers → deep house (turbo). Two strengths on pop, one on folk.
run pop-to-deephouse-045  cover --src spike/out/pop-turbo_1.wav  --lyrics spike/lyrics/pop.txt  --caption "$DEEPHOUSE" --strength 0.45 --steps 8 --shift 3 --model acestep-v15-turbo --bpm 124
run pop-to-deephouse-065  cover --src spike/out/pop-turbo_1.wav  --lyrics spike/lyrics/pop.txt  --caption "$DEEPHOUSE" --strength 0.65 --steps 8 --shift 3 --model acestep-v15-turbo --bpm 124
run folk-to-deephouse-045 cover --src spike/out/folk-turbo_1.wav --lyrics spike/lyrics/folk.txt --caption "$DEEPHOUSE" --strength 0.45 --steps 8 --shift 3 --model acestep-v15-turbo --bpm 124

# 6. Stems on the full pop take (htdemucs_ft via MLX)
if [[ ! -f "spike/out/stems/pop-turbo_1_(vocals)_htdemucs_ft.wav" ]]; then
  t0=$(date +%s)
  services/stems/.venv/bin/mlx-audio-separator -m htdemucs_ft.yaml --model_file_dir services/stems/models \
      --output_dir spike/out/stems --output_format WAV spike/out/pop-turbo_1.wav 2>&1 | grep -iE "Separation duration|complete|error" | tail -3
  echo "{\"name\": \"stems-pop-htdemucs_ft\", \"elapsed_s\": $(( $(date +%s) - t0 )), \"task\": \"stems\", \"src\": \"spike/out/pop-turbo_1.wav\"}" >> spike/out/results.jsonl
fi

echo "### matrix done $(date)"

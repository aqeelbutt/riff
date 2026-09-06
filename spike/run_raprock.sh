#!/usr/bin/env bash
# Phase 0d: rap-rock mashup preset (rapped verses + huge sung rock chorus), and rock → rap-rock cover. Idempotent.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

RAPROCK="rap rock mashup, nu-metal down-tuned distorted guitars, heavy drums, hip-hop rapped verses with confident male MC, huge anthemic sung rock chorus with a second male vocalist, turntable scratches, DJ cuts, stadium energy, 100 BPM"
ROCK_TO_RAPROCK="rap rock mashup remake, keep the sung rock chorus and guitars, add rapped hip-hop verses over a heavy boom-bap drum groove, turntable scratches, nu-metal energy, 100 BPM"

run() {
  local name="$1"; shift
  if [[ -f "spike/out/${name}_1.wav" ]]; then echo "skip $name (exists)"; return 0; fi
  python3 spike/run_spike.py "$@" --name "$name" 2>&1 | tr '\r' '\n' | grep -vE "^\s*… "
  if ! curl -sf http://127.0.0.1:8001/health >/dev/null; then
    echo "!!! engine is down after $name — scripts/engine.sh start, then re-run"; exit 1
  fi
}

curl -sf http://127.0.0.1:8001/health >/dev/null || { scripts/engine.sh start; for i in $(seq 1 40); do curl -sf http://127.0.0.1:8001/health >/dev/null && break; sleep 5; done; }
echo "### raprock start $(date)"
run raprock-turbo   text2music --lyrics spike/lyrics/raprock.txt --caption "$RAPROCK" --duration 150 --steps 8 --shift 3 --model acestep-v15-turbo --seed 4001 --bpm 100
run rock-to-raprock cover --src spike/out/rock-turbo_1.wav --lyrics spike/lyrics/raprock.txt --caption "$ROCK_TO_RAPROCK" --strength 0.45 --steps 8 --shift 3 --model acestep-v15-turbo --bpm 100
echo "### raprock done $(date)"

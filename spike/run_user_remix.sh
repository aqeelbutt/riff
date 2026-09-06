#!/usr/bin/env bash
# Remix a user-supplied song (spike/in/<file>) → emotional / chill deep house variants. Idempotent.
# usage: spike/run_user_remix.sh spike/in/aqeel-test-1.mp3 ur
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
SRC="${1:?source audio}"; LANG_CODE="${2:-en}"; BASE="$(basename "${SRC%.*}")"

EMO_DEEP="emotional melodic deep house remix, 118 BPM, chill and dreamy, lush warm analog pads, gentle piano melody lines and soft synth arpeggios answering the vocal, deep rolling sub bass, soft four-on-the-floor kick with sidechain, airy hi-hats, wide reverb and atmosphere, late-night cinematic feel, keep the original vocals"
CHILL_DEEP="chill downtempo deep house remix, 108 BPM, very relaxed and emotional, soft lo-fi drums, warm Rhodes and piano melodies, floating pads, subtle strings, deep sub bass, slow-building, intimate and dreamy, keep the original vocals"

run() {
  local name="$1"; shift
  if [[ -f "spike/out/${name}_1.wav" ]]; then echo "skip $name (exists)"; return 0; fi
  python3 spike/run_spike.py "$@" --name "$name" 2>&1 | tr '\r' '\n' | grep -vE "^\s*… "
  if ! curl -sf http://127.0.0.1:8001/health >/dev/null; then
    echo "!!! engine is down after $name — scripts/engine.sh start, then re-run"; exit 1
  fi
}
curl -sf http://127.0.0.1:8001/health >/dev/null || { scripts/engine.sh start; for i in $(seq 1 40); do curl -sf http://127.0.0.1:8001/health >/dev/null && break; sleep 5; done; }

echo "### user remix start $(date) src=$SRC"
run "${BASE}-emo-deephouse-060" cover --src "$SRC" --caption "$EMO_DEEP"   --strength 0.60 --steps 8 --shift 3 --model acestep-v15-turbo --bpm 118 --lang "$LANG_CODE"
run "${BASE}-emo-deephouse-045" cover --src "$SRC" --caption "$EMO_DEEP"   --strength 0.45 --steps 8 --shift 3 --model acestep-v15-turbo --bpm 118 --lang "$LANG_CODE"
run "${BASE}-chill-deephouse"   cover --src "$SRC" --caption "$CHILL_DEEP" --strength 0.50 --steps 8 --shift 3 --model acestep-v15-turbo --bpm 108 --lang "$LANG_CODE"
echo "### user remix done $(date)"

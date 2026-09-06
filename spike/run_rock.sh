#!/usr/bin/env bash
# Phase 0c: rock source → jazz-rap layout and → deep house (cover mode). Idempotent.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

ROCK="high-energy alternative rock, driving distorted electric guitars, pounding drums, punchy bass, powerful gritty male lead vocal, anthemic chorus, 128 BPM"
ROCK_TO_JAZZRAP="jazz rap remake, boom-bap hip-hop groove with live jazz band, warm Rhodes piano chords, upright bass, brushed drums, muted trumpet and saxophone licks, vinyl crackle, laid-back rapped and sung male vocal, deep late-night mood, 88 BPM"
ROCK_TO_DEEPHOUSE="deep house remix, 124 BPM, four-on-the-floor kick, sidechained warm pads, filtered chord stabs, rolling sub bass, shuffled hi-hats, late-night club atmosphere, keep the vocals"

run() {
  local name="$1"; shift
  if [[ -f "spike/out/${name}_1.wav" ]]; then echo "skip $name (exists)"; return 0; fi
  python3 spike/run_spike.py "$@" --name "$name" 2>&1 | tr '\r' '\n' | grep -vE "^\s*… "
  if ! curl -sf http://127.0.0.1:8001/health >/dev/null; then
    echo "!!! engine is down after $name — scripts/engine.sh start, then re-run"; exit 1
  fi
}

echo "### rock start $(date)"
run rock-turbo text2music --lyrics spike/lyrics/rock.txt --caption "$ROCK" --duration 150 --steps 8 --shift 3 --model acestep-v15-turbo --seed 3001 --bpm 128

# strength 0.4 for the big genre jump (rock → jazz-rap), 0.5 for rock → deep house
run rock-to-jazzrap   cover --src spike/out/rock-turbo_1.wav --lyrics spike/lyrics/rock.txt --caption "$ROCK_TO_JAZZRAP"   --strength 0.4 --steps 8 --shift 3 --model acestep-v15-turbo --bpm 88
run rock-to-deephouse cover --src spike/out/rock-turbo_1.wav --lyrics spike/lyrics/rock.txt --caption "$ROCK_TO_DEEPHOUSE" --strength 0.5 --steps 8 --shift 3 --model acestep-v15-turbo --bpm 124
echo "### rock done $(date)"

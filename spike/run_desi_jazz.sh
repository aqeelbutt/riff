#!/usr/bin/env bash
# Phase 0b: jazz-rap preset + Indian/Pakistani language + remix checks. Idempotent like run_matrix.sh.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

JAZZRAP="jazz rap, boom-bap hip-hop with live jazz band, warm Rhodes piano chords, upright bass, brushed drums, muted trumpet and saxophone licks, vinyl crackle, laid-back confident male rap vocal, deep late-night mood, 88 BPM"
HINDI="romantic Bollywood ballad, Hindi vocals, soft sitar and strings intro, tabla groove, harmonium, bansuri flute, warm male lead vocal with gentle ornamentation, emotional and cinematic, 92 BPM"
URDU="Pakistani sufi pop, Urdu vocals, harmonium, dholak and tabla, qawwali-style claps, powerful soulful male lead vocal with melismatic runs, building to an ecstatic chorus, 96 BPM"
DESI_DEEPHOUSE="Bollywood deep house remix, 124 BPM, four-on-the-floor kick, sidechained warm pads, filtered chord stabs, rolling sub bass, tabla percussion layered over the groove, late-night club atmosphere, keep the original Hindi vocals"
SUFI_HOUSE="sufi deep house remix, 122 BPM, four-on-the-floor kick, deep sub bass, hypnotic harmonium drone over warm pads, dholak percussion, keep the original Urdu vocals, trance-like build"

run() {
  local name="$1"; shift
  if [[ -f "spike/out/${name}_1.wav" ]]; then echo "skip $name (exists)"; return 0; fi
  python3 spike/run_spike.py "$@" --name "$name" 2>&1 | tr '\r' '\n' | grep -vE "^\s*… "
  if ! curl -sf http://127.0.0.1:8001/health >/dev/null; then
    echo "!!! engine is down after $name — scripts/engine.sh start, then re-run"; exit 1
  fi
}

echo "### desi+jazz start $(date)"

# 1. Jazz-rap preset (English)
run jazzrap-turbo text2music --lyrics spike/lyrics/jazzrap.txt --caption "$JAZZRAP" --duration 150 --steps 8 --shift 3 --model acestep-v15-turbo --seed 2001 --bpm 88

# 2. Hindi: romanized vs Devanagari, same seed, vocal_language=hi
run hindi-roman-turbo text2music --lyrics spike/lyrics/hindi-roman.txt      --caption "$HINDI" --duration 150 --steps 8 --shift 3 --model acestep-v15-turbo --seed 2002 --bpm 92 --lang hi
run hindi-deva-turbo  text2music --lyrics spike/lyrics/hindi-devanagari.txt --caption "$HINDI" --duration 150 --steps 8 --shift 3 --model acestep-v15-turbo --seed 2002 --bpm 92 --lang hi

# 3. Urdu: romanized vs Nastaliq script, same seed, vocal_language=ur
run urdu-roman-turbo  text2music --lyrics spike/lyrics/urdu-roman.txt  --caption "$URDU" --duration 150 --steps 8 --shift 3 --model acestep-v15-turbo --seed 2003 --bpm 96 --lang ur
run urdu-script-turbo text2music --lyrics spike/lyrics/urdu-script.txt --caption "$URDU" --duration 150 --steps 8 --shift 3 --model acestep-v15-turbo --seed 2003 --bpm 96 --lang ur

# 4. Remix the Hindi + Urdu tracks → desi deep house (the user's actual use case, on rights-clean sources)
run hindi-to-deephouse cover --src spike/out/hindi-roman-turbo_1.wav --lyrics spike/lyrics/hindi-roman.txt --caption "$DESI_DEEPHOUSE" --strength 0.5 --steps 8 --shift 3 --model acestep-v15-turbo --bpm 124 --lang hi
run urdu-to-deephouse  cover --src spike/out/urdu-roman-turbo_1.wav  --lyrics spike/lyrics/urdu-roman.txt  --caption "$SUFI_HOUSE"     --strength 0.5 --steps 8 --shift 3 --model acestep-v15-turbo --bpm 122 --lang ur

# 5. Stems on the Hindi track: do tabla/harmonium/sitar separate sensibly? (engine idle now — one GPU workload at a time)
if [[ ! -f "spike/out/stems/hindi-roman-turbo_1_(vocals)_htdemucs_ft.wav" ]]; then
  t0=$(date +%s)
  services/stems/.venv/bin/mlx-audio-separator -m htdemucs_ft.yaml --model_file_dir services/stems/models \
      --output_dir spike/out/stems --output_format WAV spike/out/hindi-roman-turbo_1.wav 2>&1 | grep -iE "Separation duration|complete|error" | tail -2
  echo "{\"name\": \"stems-hindi-htdemucs_ft\", \"elapsed_s\": $(( $(date +%s) - t0 )), \"task\": \"stems\", \"src\": \"spike/out/hindi-roman-turbo_1.wav\"}" >> spike/out/results.jsonl
fi

echo "### desi+jazz done $(date)"

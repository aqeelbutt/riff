# Riff

An AI music studio in the spirit of Suno, running on your own machine. Give it a few keywords, Claude writes the lyrics, and a local music model (ACE-Step 1.5) renders a full song with vocals in any genre. Drop in an existing track and get it back as deep house, lo-fi, drum & bass, or any style you describe.

**Status:** Phase 0 (engine spike) — see [`docs/RIFF_V1_PLAN.md`](./docs/RIFF_V1_PLAN.md) for the plan and [`docs/PHASE0_SPIKE.md`](./docs/PHASE0_SPIKE.md) for the spike results.

## Engine quick start (macOS, Apple Silicon)

```bash
git clone --recurse-submodules git@github.com:aqeelbutt/riff.git && cd riff
scripts/engine.sh install     # uv sync + ~15 GB of weights into services/ace-step/checkpoints/
scripts/engine.sh start       # REST API on http://127.0.0.1:8001
scripts/engine.sh status
python3 spike/run_spike.py text2music --name demo --lyrics spike/lyrics/pop.txt \
  --caption "upbeat modern pop anthem, female lead vocal, 118 BPM" --duration 150 --steps 8 --shift 3 --model acestep-v15-turbo
```

Requires `uv`, `ffmpeg`, and roughly 40 GB of free disk for the first install.

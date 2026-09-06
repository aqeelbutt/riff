#!/usr/bin/env bash
# Riff audio tools venv (stems, lyrics, stretch, mastering) — install | status
#   demucs (Meta reference, PyTorch on MPS)  · mlx-whisper (large-v3)  · pyrubberband  · librosa  · pyloudnorm
# NOTE: mlx-audio-separator is deliberately NOT used (broken output — see CLAUDE.md).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; D="$ROOT/services/stems"; export PATH="$HOME/.local/bin:$PATH"
case "${1:-}" in
  install)
    command -v uv >/dev/null || { echo "uv not found: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2; exit 1; }
    command -v rubberband >/dev/null || brew install rubberband
    command -v ffmpeg >/dev/null || brew install ffmpeg
    mkdir -p "$D" && cd "$D" && [[ -d .venv ]] || uv venv --python 3.12 .venv
    uv pip install --python .venv/bin/python demucs mlx-whisper pyrubberband librosa pyloudnorm soundfile
    echo "pre-caching models (demucs htdemucs_ft ~330 MB, whisper-large-v3-mlx ~3 GB)…"
    .venv/bin/python -c "from demucs.pretrained import get_model; get_model('htdemucs_ft')" >/dev/null 2>&1 || true
    .venv/bin/python -c "import mlx_whisper, numpy as np; mlx_whisper.transcribe(np.zeros(16000,dtype='float32'), path_or_hf_repo='mlx-community/whisper-large-v3-mlx')" >/dev/null 2>&1 || true
    echo "audio tools ready: $D/.venv" ;;
  status)
    "$D/.venv/bin/python" -c "import demucs, mlx_whisper, pyrubberband, librosa, pyloudnorm; print('tools ok')" ;;
  *) echo "usage: $0 {install|status}" >&2; exit 2 ;;
esac

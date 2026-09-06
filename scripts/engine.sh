#!/usr/bin/env bash
# Riff music engine sidecar (ACE-Step 1.5) — install / start / stop / status.
#
#   scripts/engine.sh install   # uv sync + download core bundle (turbo 2B + LM 1.7B + VAE) + SFT
#   scripts/engine.sh start     # REST API on http://127.0.0.1:8001 (MLX backend, turbo slot 1, SFT slot 2)
#   scripts/engine.sh stop
#   scripts/engine.sh status
#
# The engine is a pinned git submodule at services/ace-step (see .gitmodules).
# Model weights live in services/ace-step/checkpoints/ (gitignored, ~15 GB).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE_DIR="$ROOT/services/ace-step"
LOG_DIR="$ROOT/var/log"
PID_FILE="$ROOT/var/engine.pid"
PORT="${ACESTEP_API_PORT:-8001}"
export PATH="$HOME/.local/bin:$PATH"

# Apple Silicon: MLX for the LM, MPS for the DiT. Auto-selected on other hosts.
if [[ "$(uname)" == "Darwin" && "$(uname -m)" == "arm64" ]]; then
  export ACESTEP_LM_BACKEND="${ACESTEP_LM_BACKEND:-mlx}"
fi
export TOKENIZERS_PARALLELISM=false
export ACESTEP_CONFIG_PATH="${ACESTEP_CONFIG_PATH:-acestep-v15-turbo}"
export ACESTEP_CONFIG_PATH2="${ACESTEP_CONFIG_PATH2:-acestep-v15-sft}"
export ACESTEP_INIT_LLM="${ACESTEP_INIT_LLM:-true}"
export ACESTEP_LM_MODEL_PATH="${ACESTEP_LM_MODEL_PATH:-acestep-5Hz-lm-1.7B}"

need_engine() {
  if [[ ! -f "$ENGINE_DIR/pyproject.toml" ]]; then
    echo "services/ace-step is empty — run: git submodule update --init" >&2
    exit 1
  fi
}

case "${1:-}" in
  install)
    need_engine
    command -v uv >/dev/null || { echo "uv not found: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2; exit 1; }
    (cd "$ENGINE_DIR" && uv sync --python 3.12)
    (cd "$ENGINE_DIR" && uv run --offline acestep-download)
    (cd "$ENGINE_DIR" && uv run --offline acestep-download --skip-main --model acestep-v15-sft)
    echo "engine installed: $(du -sh "$ENGINE_DIR/checkpoints" | cut -f1) of weights"
    ;;
  start)
    need_engine
    mkdir -p "$LOG_DIR" "$(dirname "$PID_FILE")"
    if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      echo "engine already running (pid $(cat "$PID_FILE"))"; exit 0
    fi
    (cd "$ENGINE_DIR" && nohup uv run --offline acestep-api --host 127.0.0.1 --port "$PORT" \
        > "$LOG_DIR/engine.log" 2>&1 & echo $! > "$PID_FILE")
    echo "engine starting (pid $(cat "$PID_FILE")) → log: $LOG_DIR/engine.log"
    echo "first start loads ~10 GB of weights; poll: scripts/engine.sh status"
    ;;
  stop)
    if [[ -f "$PID_FILE" ]]; then
      kill "$(cat "$PID_FILE")" 2>/dev/null && echo "engine stopped" || echo "engine was not running"
      rm -f "$PID_FILE"
    else
      pkill -f "acestep-api" && echo "engine stopped" || echo "engine was not running"
    fi
    ;;
  status)
    if curl -sf "http://127.0.0.1:$PORT/health" >/dev/null; then
      curl -s "http://127.0.0.1:$PORT/health"; echo
      curl -s "http://127.0.0.1:$PORT/v1/models"; echo
    else
      echo "engine not responding on :$PORT"
      [[ -f "$LOG_DIR/engine.log" ]] && tail -5 "$LOG_DIR/engine.log"
      exit 1
    fi
    ;;
  *)
    echo "usage: $0 {install|start|stop|status}" >&2; exit 2 ;;
esac

#!/usr/bin/env bash
# `pnpm dev`: Postgres + Redis (docker) → migrations → music engine → API (:8010) → web (:3000). Ctrl-C stops all.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"; export PATH="$HOME/.local/bin:$ROOT/bin:$PATH"
docker compose up -d
until docker compose exec -T postgres pg_isready -U riff -d riff >/dev/null 2>&1; do sleep 1; done
[[ -f apps/backend/.env ]] || cp apps/backend/.env.example apps/backend/.env
(cd apps/backend && uv run --offline alembic upgrade head)
scripts/engine.sh start || true
mkdir -p var/log
(cd apps/backend && exec uv run --offline uvicorn app.main:app --reload --port 8010) &
API=$!
(cd apps/web && exec pnpm dev) &
WEB=$!
trap 'kill $API $WEB 2>/dev/null; exit 0' INT TERM
echo; echo "  API   http://127.0.0.1:8010/health"; echo "  Web   http://localhost:3000"; echo "  Engine http://127.0.0.1:8001/health"; echo
wait

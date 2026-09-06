#!/usr/bin/env bash
# Riff backend tests. Needs Postgres from `pnpm docker:up` (port 5433). Usage: ./run_tests.sh [file] [-k pattern]
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
export APP_ENV=test MUSIC_PROVIDER=fake WORKER_ENABLED=false MASTERING_ENABLED=false
export DATABASE_URL="postgresql+asyncpg://riff:riff_dev@localhost:5433/riff_test"
export MEDIA_ROOT="$(mktemp -d)/media"
exec uv run --offline pytest -q "$@"

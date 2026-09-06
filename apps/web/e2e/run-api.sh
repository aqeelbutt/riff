#!/usr/bin/env bash
# E2E API: fake music + fake lyrics providers on a dedicated DB (riff_e2e) and port 8011. Deterministic, seconds not minutes.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../../backend"; export PATH="$HOME/.local/bin:$PATH"
export APP_ENV=test MUSIC_PROVIDER=fake LYRICS_PROVIDER=fake AUDIO_TOOLS=fake WORKER_ENABLED=true MASTERING_ENABLED=false JOB_POLL_SECONDS=0.3
export DATABASE_URL="postgresql+asyncpg://riff:riff_dev@localhost:5433/riff_e2e" MEDIA_ROOT="${TMPDIR:-/tmp}/riff-e2e-media" CORS_ORIGINS="http://localhost:3100,http://127.0.0.1:3100"
docker exec riff-postgres psql -U riff -d riff -tAc "SELECT 1 FROM pg_database WHERE datname='riff_e2e'" | grep -q 1 || docker exec riff-postgres psql -U riff -d riff -c "CREATE DATABASE riff_e2e" >/dev/null
uv run --offline alembic upgrade head >/dev/null
docker exec riff-postgres psql -U riff -d riff_e2e -c "TRUNCATE TABLE remixes, stems, uploads, generations, jobs, songs, users, ai_call_telemetry CASCADE" >/dev/null
exec uv run --offline uvicorn app.main:app --port 8011

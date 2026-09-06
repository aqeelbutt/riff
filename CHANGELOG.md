# Changelog

Every release folds the fragments queued in [`changelog.d/`](./changelog.d) into a dated section.

## [1.0.0] — 2026-09-06

### Added

- Boom-Bap style preset (Create + a "Boom-Bap Flip" remix target) and `GET /presets`, the style registry both surfaces render from.
- Phase 1 scaffold: pnpm/turbo monorepo; FastAPI backend (`apps/backend`) with songs/generations/jobs, a single-lane DB job runner (SKIP LOCKED claim, heartbeat, reaper, idempotency), the `MusicProvider` seam (ACE-Step sidecar + a FakeProvider for tests), LocalFS storage, ffmpeg mastering; a minimal Next.js status page (`apps/web`); `pnpm dev` brings up Postgres, migrations, the engine, the API and the web.
- Create screen (Phase 2): Claude writes a structured song brief and streams the lyrics into a section editor with per-section rewrites; generate two takes with real stage progress, waveforms, A/B and keep. `POST /lyrics/{brief,write,section}` with per-call `ai_call_telemetry` (tokens + USD).
- Library (Phase 3): song grid with search/filters/sort, song page with takes by run, keep/remove/download, rename, more takes, delete; one app-wide player with A/B that follows you between pages. `GET /songs` search/filter params, `DELETE /songs/{id}`, `DELETE /generations/{id}`. Playwright E2E for the whole Create→Library journey on fake providers.
- Remix (Phase 4): upload a song you own or pick one of your takes → stems (Demucs), tempo/key, lyrics (Whisper on the vocal stem) → style presets, your-voice modes, closeness, tempo → your real vocal auto-tuned (default on) and in front, AI vocals separated and ducked underneath (hybrid), two variations per run, A/B result. `POST /uploads`, `/uploads/from-generation/{gen}`, `/uploads/{id}/remix`, `GET /remixes…`. Remix E2E on fake tools.
- Hardening for 1.0: `scripts/engine.sh supervise` keeps the music engine alive (health check, restart, backoff) and `pnpm dev` runs it that way; the web shows a calm, actionable banner naming whichever of API / database / engine / worker is down and the command that fixes it; `docs/ENGINE_RUNBOOK.md`; `scripts/assemble_changelog.py` and `scripts/release_check.sh` (version literals, tests, build, clean tree) gate a release.
- Reimagine (the new default in Remix): Claude reads your song — meaning, chorus, emotional arc — and writes a full arrangement in its own key, which the engine performs, instead of pushing the recording into a beat. Six directions plus free text; "Let it be sung" or "Keep my voice" (the arrangement is played at your tempo so your auto-tuned vocal lines up); the result shows Claude's reading beside the audio.

### Changed

- Create: the compose panel collapses to a rail and can be widened (remembered); Voice and Language each get a full row so nothing overlaps.
- Ports moved so Riff runs alongside PursuitAI: web 3010 (was 3000); API 8010, Postgres 5433, Redis 6380, engine 8001 unchanged.


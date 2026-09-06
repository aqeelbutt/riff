# CLAUDE.md — Riff

AI music studio (Suno-style): keywords → Claude writes the lyrics → a local music model renders a full song with vocals in any genre; or take an existing track and re-render it as deep house / another style. **V1 is local-first, single-user, no auth**; built so V2 can go hosted + mobile additively. Plan + roadmap: [`docs/RIFF_V1_PLAN.md`](./docs/RIFF_V1_PLAN.md). Phase 0 engine spike results: [`docs/PHASE0_SPIKE.md`](./docs/PHASE0_SPIKE.md).

This repo follows the same harness as PursuitAI: pnpm + turbo monorepo, `apps/backend` (FastAPI, async SQLAlchemy, Alembic), `apps/web` (Next.js 15, Tailwind, vitest + RTL, Playwright), Postgres + Redis via docker-compose. Conventions carried over verbatim: feature branch → `develop` (squash), `develop → main` merge commit; `changelog.d/` fragments, never a direct `CHANGELOG.md` edit; every new setting lands in `.env.example` in the same PR; every web UI behaviour change ships a vitest test; **clickable mock before any screen** (UI brief: intuitive and easy to use first, then a cool modern design — never a default-template look); a module that opens its own DB session gets a conftest redirect fixture; charge-after-validation on every Claude call; no hardcoded colors, theme tokens only.

## Layout

- `services/ace-step/` — **the music engine sidecar: ACE-Step 1.5, a pinned git submodule** (`git submodule update --init`). MIT, runs natively on Apple Silicon (MLX for LM/DiT/VAE). Own `uv` venv inside the submodule; weights in `services/ace-step/checkpoints/` (gitignored, ~15 GB: turbo 2B + SFT + LM 1.7B + VAE). Never import it from the backend — the backend only speaks HTTP to it.
- `scripts/engine.sh` — `install | start | stop | status` for the sidecar. Encodes the Phase 0 startup recipe (one DiT slot, LM lazy-loaded, `PYTHONFAULTHANDLER=1`). REST API on `http://127.0.0.1:8001` (`POST /release_task` → `POST /query_result` → `GET /v1/audio?path=`; `POST /v1/init` switches models; docs in `services/ace-step/docs/en/API.md`).
- `services/stems/` — stem separation venv (`mlx-audio-separator[convert]` — the `[convert]` extra is REQUIRED or htdemucs fails to load); model `htdemucs_ft.yaml` in `services/stems/models/`. 4 stems (vocals/drums/bass/other) from a 150 s song in ~5 s on the M4 Pro.
- `spike/` — Phase 0 harness: `run_spike.py` (stdlib REST client; `text2music | cover | init | status`), `run_matrix.sh` (idempotent timing matrix), `lyrics/` (three original fixtures). Outputs in `spike/out/` (gitignored); `spike/out/results.jsonl` is the timing ledger.
- `apps/`, `docs/`, `changelog.d/` — per the plan; scaffolded from Phase 1.

## Engine gotchas (learned in Phase 0)

- **The sidecar can die silently.** Three times in the spike the process vanished with no traceback (a Metal-level kill): twice during VAE decode, once idle. It never reproduced across 16 renders under every startup combination — but all three deaths overlapped **another MLX/torch process starting on the box** (stem separator loading, a torch wheel install). Working rule: **one GPU workload at a time** — the job runner serializes renders and stem jobs on a single GPU lane, never launches the stems tool during a render. Also: treat a dropped connection as a retryable failure, and give the sidecar a supervisor/health check. Don't spend a session bisecting it again — the finding and the bisect matrix are in `docs/PHASE0_SPIKE.md`.
- **Don't pre-load two DiT slots.** `ACESTEP_CONFIG_PATH2` keeps a second full model + a second compiled MLX VAE resident. Switch models on demand with `POST /v1/init {"model": "acestep-v15-sft"}` (~20 s) instead.
- **The 5Hz LM is optional.** `thinking=false` skips it; the product's Claude "song brief" supplies BPM/key/structure. Load it lazily only for a feature that needs it; it's auto-skipped for `cover`/`repaint` anyway.
- **Turbo needs `shift=3.0`** (not auto-corrected, unlike `guidance_scale`). 8 steps.
- **Always pass `bpm` and `vocal_language`.** The caption's "118 BPM" is ignored without the LM; `vocal_language` defaults to `"en"` so Hindi/Urdu lyrics must send `hi`/`ur`. Romanized and native-script lyrics both work. Cover strength ≥0.5 keeps the SOURCE tempo; use ~0.4 for a tempo/genre jump.
- **Style presets are data, not code** — caption template + default strength + target BPM. The engine's `genres_vocab.txt` already covers Bollywood/filmi, Punjabi/bhangra, qawwali, ghazal, sufi, Urdu pop, jazz-rap/jazz-hop, boom-bap, neo-soul.
- **XL models (20 GB each) don't fit** on this Mac without freeing disk (~21 GB free after install).
- Reference/source audio for `cover` goes up as `multipart/form-data` (`src_audio` file field); JSON paths must be absolute on the server.
- zsh doesn't word-split unquoted variables — in scripts use `"$@"`/arrays, not `R="cmd args"; $R`.

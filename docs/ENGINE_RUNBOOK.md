# Engine runbook

The music engine (ACE-Step 1.5) is a separate process. Everything else in Riff keeps working when it's down — you just
can't render. This is what to do when it misbehaves.

## Normal operation

```bash
scripts/engine.sh start      # background, ~10 s to answer /health, loads ~10 GB of weights on the first request
scripts/engine.sh status     # health + which models are resident
scripts/engine.sh supervise  # health-check loop that restarts it if it dies — what `pnpm dev` runs
scripts/engine.sh stop
```

Logs: `var/log/engine.log` (the engine itself) and `var/log/engine-supervisor.log` (restarts).
The API reports it too: `GET http://127.0.0.1:8010/health` → `engine: {ok, loaded_model, …}`, and the web header shows a
green dot when it's up, "engine offline" when it isn't.

## It died silently

**Symptom:** renders stop, `status` says not responding, `var/log/engine.log` ends mid-decode with no traceback — often
with `resource_tracker: There appear to be 1 leaked semaphore objects`.

**Cause (working theory, Phase 0):** a second Metal/MLX client starting while the engine holds ~10 GB of GPU buffers gets
the engine killed by the OS. All three observed deaths coincided with another GPU process starting.

**What to do:** nothing manual — the supervisor restarts it within ~20 s and the job runner retries the job (three
attempts, then the job is marked failed and the UI says so). If you're running the engine unsupervised, `start` it again.

**What to avoid:** one GPU workload at a time. Don't run `riff` CLI commands, Demucs or Whisper by hand while the API
worker is rendering — the API serializes its own work on a single lane, but it can't see processes you start yourself.

## It won't start

| Symptom | Fix |
|---|---|
| `services/ace-step is empty` | `git submodule update --init` |
| `uv not found` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Import errors / missing wheels | `cd services/ace-step && uv sync --python 3.12` |
| Weights missing, first render 404s | `scripts/engine.sh install` (re-runs the downloads; ~15 GB) |
| Out of disk | weights live in `services/ace-step/checkpoints/`; renders pile up in `var/media/` and `var/out/` |

## It's slow

Turbo renders 150 s of audio in roughly 30 s on an M4 Pro. If it's much slower, check that something else isn't using the
GPU, and that you're not on the Studio model (50 steps, about 6× slower — that's expected).

The first request after a start pays the model load (~30 s). `POST /v1/init` warms it deliberately.

## Running without the engine

Set `MUSIC_PROVIDER=fake` in `apps/backend/.env` to develop the app with instant silent takes, and `AUDIO_TOOLS=fake` to
skip Demucs/Whisper. That's exactly what the test suite and the E2E run on, so the whole product is exercisable with no
GPU at all.

## Where the audio goes

| Path | What |
|---|---|
| `var/media/generations/<song>/<batch>/` | Create renders (WAV + mastered MP3) |
| `var/media/uploads/<upload>/` | an uploaded song, its `stems/`, and its `remixes/` |
| `var/out/<name>/` | anything the `riff` CLI made |

Deleting a song or an upload in the app removes its folder too.

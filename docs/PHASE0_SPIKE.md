# Phase 0 — Engine spike results

**Date:** 2026-09-06 · **Host:** Apple M4 Pro, 48 GB unified memory, macOS 26 · **Engine:** ACE-Step 1.5 at submodule commit `ca1e85f` (2026-08-29), MLX backend for LM + DiT + VAE · **Stems:** `mlx-audio-separator` 0.1.7, `htdemucs_ft`.

**Engineering verdict: GO.** The engine does both product pillars (text → full song with vocals; audio → restyled cover) at interactive speeds on this laptop, at zero per-song cost. **The quality verdict is yours** — listen to the files in §4 in that order; that is the only Phase 0 exit criterion still open.

## 1. What was measured

Every run is a line in `spike/out/results.jsonl` (wall-clock from `POST /release_task` to the WAV on disk, including download). Full-song runs are **150 s of audio** with the original lyrics in `spike/lyrics/`. Turbo = 8 steps, `shift=3`; SFT = 50 steps with CFG.

| Run | What | Wall-clock | Audio | Speed vs realtime |
|---|---|---:|---:|---:|
| `pop-turbo` | pop anthem, female vocal, turbo | **30 s** | 150 s | 5.0× |
| `hiphop-turbo` | trap-influenced hip-hop, male rap | **36 s** | 150 s | 4.2× |
| `folk-turbo` | acoustic folk-country, male vocal | **27 s** | 150 s | 5.5× |
| `pop-turbo-think` | same pop, 5Hz LM planning on (`thinking=true`) | 54 s | 150 s | 2.8× |
| `pop-turbo-batch2` | same pop, **2 variations in one batch** (the product default) | 57 s | 2 × 150 s | 5.3× |
| `pop-sft` | same pop, SFT 50 steps ("higher quality, slower") | 181 s | 150 s | 0.8× |
| `pop-to-deephouse-045` | cover of `pop-turbo` → deep house, strength 0.45 | 86 s * | 150 s | 1.7× |
| `pop-to-deephouse-065` | same, strength 0.65 | 43 s | 150 s | 3.5× |
| `folk-to-deephouse-045` | cover of `folk-turbo` → deep house, strength 0.45 | 50 s | 150 s | 3.0× |
| `stems-pop-htdemucs_ft` | 4 stems (vocals/drums/bass/other) from `pop-turbo` | 51 s | 150 s | 2.9× |
| 30-s probes (×5) | bisect runs, various startup configs | 9–37 s (76 s cold) | 30 s | — |

\* first cover on this server (includes the source-audio encode warm-up); the next two covers were 43–50 s.

Model load: turbo DiT + VAE + LM 1.7B into memory in **28 s** (`POST /v1/init`); a cold server answers `/health` in ~10 s and lazy-loads on the first request. Diffusion itself is ~1.2 s/step for 150 s of audio; VAE decode ~13 s for 150 s.

**Read for the product:** a Suno-style "two takes" generation is about **one minute** on turbo. The plan's 1–4 min estimate was pessimistic. SFT at 3 min is a legitimate "final version" toggle, not the default.

## 2. Objective checks on the audio

Measured with librosa (beat tracking) and pyloudnorm on the WAVs — these are things a listener can't easily judge and the product must handle.

| File | Detected BPM | Integrated LUFS | Peak |
|---|---:|---:|---:|
| `pop-turbo` | 176 (= 2 × 88) | −19.6 | 0.63 |
| `pop-turbo-think` (LM planning on) | 115 | −18.6 | 0.72 |
| `pop-sft` | 176 (= 2 × 88) | −17.1 | 0.76 |
| `pop-to-deephouse-045` | **125** | −18.7 | 0.75 |
| `pop-to-deephouse-065` | **125** | −17.3 | 0.79 |
| `folk-turbo` | 161 (≈ 2 × 80) | −16.7 | 0.84 |
| `folk-to-deephouse-045` | **125** | −19.3 | 0.88 |
| `hiphop-turbo` | 161 | −17.1 | 0.89 |

Two findings that change the build:

1. **Cover mode really re-tempos to the style prompt.** All three deep-house covers land at 125 BPM against the 124 BPM caption + explicit `bpm=124`, from sources at ~88 and ~80 BPM. That is the remix pillar working at the engine level.
2. **Without the LM, the caption's BPM is not honored.** The plain-turbo pop track came out at 88 BPM despite "118 BPM" in the caption; with `thinking=true` it came out at 115. The engine's own metadata (`metas.bpm`) confirms it. → **The backend must pass `bpm` (and key) explicitly from the Claude song brief on every render** — the API accepts them as fields — instead of relying on the caption text or the 5Hz LM. That makes the LM optional for V1 (Claude is the planner), which is also cheaper on memory and avoids the 2× time cost of `thinking=true`.

Also: raw output sits at **−17 to −20 LUFS with peaks well under 0 dBFS** — un-mastered. The product's post-render step should loudness-normalize to about −14 LUFS (streaming standard) with a true-peak limiter; pyloudnorm is already in the stems venv.

## 3. The crash, and what to do about it

The engine process **died twice, silently, during VAE decode** — the very first render on each of the first two server starts. No Python traceback, no macOS crash report, just a reset connection and the "leaked semaphore" line the interpreter prints on the way out (a Metal-level kill, not an app error). It **never reproduced in the next 16 renders**, across every startup combination I could bisect:

| Startup config | Result |
|---|---|
| LM at startup + second SFT DiT slot (the two crashing runs' config) | died ×2, then survived when re-tried (76 s cold render) |
| no LM, one slot | ok |
| second SFT slot, no LM | ok |
| LM at startup, one slot | ok |
| LM loaded after the first render | ok |
| 10 s / 30 s / 150 s renders | ok |

Upstream has fixed MLX↔MPS "command buffer double-commit" crashes in this area before (v0.1.7 notes), so this is a known class of bug in a young, fast-moving project. **Don't spend a session bisecting it again.** Design for it:

- `scripts/engine.sh` now encodes the safest recipe: **one DiT slot**, **LM lazy** (`ACESTEP_INIT_LLM=false`), `PYTHONFAULTHANDLER=1` so a native crash at least leaves a Python stack next time.
- The V1 job runner treats a dropped connection / 5xx from the sidecar as a **retryable failure** (already in the plan's reaper + `MAX_ATTEMPTS`), and the sidecar gets a **supervisor + health check** so it restarts itself.
- Model switching (turbo ⇄ SFT) via `POST /v1/init`, never two resident DiTs.

## 4. Listen to these, in this order

All in `spike/out/share/*.mp3` (WAVs in `spike/out/`).

1. **`pop-turbo_1.mp3`** — the default path: turbo, one take, 30 s render. *Is the vocal clear? Are the lyrics intelligible? Does the chorus lift?*
2. **`pop-sft_1.mp3`** — same seed and lyrics, SFT. *Is the 6× time cost audible?* If not, SFT is a hidden toggle, not a headline.
3. **`pop-turbo-think_1.mp3`** — same, with the 5Hz LM planning. *Does LM planning sound better than passing BPM explicitly would?* (Decides whether the LM ships at all.)
4. **`pop-to-deephouse-045_1.mp3`** vs **`pop-to-deephouse-065_1.mp3`** — the remix pillar. *Is the song recognizable? Does it sound like deep house? Which strength is the better default?*
5. **`folk-to-deephouse-045_1.mp3`** — the hard case (acoustic → club).
6. **`hiphop-turbo_1.mp3`**, **`folk-turbo_1.mp3`** — genre breadth.
7. **`pop-turbo-batch2_1/2.mp3`** — two random-seed takes; the "pick your favorite" experience.
8. **`pop-turbo_1_vocals-stem.mp3`** — the isolated vocal from Demucs. *Clean enough to re-layer over a regenerated bed (the Vocal-keep remix mode)?*

## 5. Decisions this spike settles

- **Engine: ACE-Step 1.5 local, turbo default, SFT as an opt-in "final quality" render.** XL (4B) models were not tested — 20 GB each doesn't fit alongside the core bundle on this disk (~21 GB free after install). Revisit if disk is freed; the API is identical.
- **The 5Hz LM is not on the V1 critical path.** Claude's song brief supplies BPM / key / structure and the backend passes them as explicit fields.
- **Two takes per generation ≈ 1 min** → the Create flow's progress UI can show real stage boundaries (queued → rendering → decoding → mastering) with a ~60 s expectation, not a multi-minute wait.
- **Remix Cover mode is real**; Vocal-keep mode is worth building (stems are clean and fast) but stays flag-gated per the plan.
- **Post-render mastering step is required** (loudness normalize + true-peak limit).
- **Engine reliability is a design input**: supervised sidecar, retryable jobs.

## 6. Reproduce

```bash
scripts/engine.sh install && scripts/engine.sh start
python3 spike/run_spike.py init --model acestep-v15-turbo --slot 1     # optional warm-up
./spike/run_matrix.sh                                                   # idempotent; ~12 min
```

Stems: `services/stems/.venv/bin/mlx-audio-separator -m htdemucs_ft.yaml --model_file_dir services/stems/models --output_dir out --output_format WAV song.wav`.

## 7. Follow-ups

- Vocal-keep remix prototype (stem → time-stretch to target BPM → cover the instrumental only → re-layer): not run in this spike.
- Extend / repaint / lego task types: untested, not in V1 scope.
- XL model quality: blocked on disk.
- Language coverage: English only tested (engine claims 50+).

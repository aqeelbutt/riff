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

**A third death, after the matrix finished:** the server exited silently while idle, and the log's last lines coincide with the stem separator (`mlx-audio-separator`, its own MLX process) loading its model at 14:44:57. That is the first pattern that fits all three: the second crash also overlapped a heavy install (`torch` wheels for the stems venv) and the first overlapped my early stem-tool probing. **Working hypothesis: a second Metal/MLX client starting while the engine holds ~10 GB of GPU buffers gets the engine killed** (GPU working-set pressure, no signal to Python). Not proven — but it costs nothing to design around and is consistent with everything seen.

Upstream has fixed MLX↔MPS "command buffer double-commit" crashes in this area before (v0.1.7 notes), so this is a known class of bug in a young, fast-moving project. **Don't spend a session bisecting it again.** Design for it:

- **One GPU workload at a time.** The V1 job runner has a single GPU lane: render jobs and stem-separation jobs are serialized, never concurrent, and the stems tool is never launched while a render is in flight. (Same rule for any future MLX/torch process on the box.)

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

---

# Phase 0b/0c — jazz-rap, Hindi/Urdu, and rock-to-anything (same day)

Follow-up renders for three requests: (a) a "hip-hop/rap with jazz" style, (b) remixing Indian and Pakistani songs, (c) rock → jazz-rap layout and rock → deep house. Scripts: `spike/run_desi_jazz.sh`, `spike/run_rock.sh`; fixtures in `spike/lyrics/` (`jazzrap`, `hindi-roman`, `hindi-devanagari`, `urdu-roman`, `urdu-script`, `rock`). Sources for the remix tests were rendered here first so every cover is rights-clean.

## Are extra dependencies needed for Indian/Pakistani songs? **No.**

- **Vocals in Hindi and Urdu are native to the engine.** Hindi is on its language list; Urdu rendered fine. The one thing that matters is the API's **`vocal_language` field (default `"en"`)** — pass `hi` / `ur` / `pa` / `bn` explicitly; it is now a `--lang` flag in the runner and becomes a language picker in the product.
- **Both scripts work.** Romanized ("Hinglish"/Roman Urdu) and native script (Devanagari, Nastaliq) fed the same seed produced audio with identical tempo/loudness measurements — the engine tokenizes both. Which sounds more natural is a listening question (files below).
- **The genre vocabulary already covers the space**: Bollywood (80s/90s filmi, R&B Bollywood pop), Punjabi pop, bhangra (567 entries), qawwali (40), ghazal (324), sufi (109), Urdu pop, Hindustani/Carnatic classical, "Desi pop". Style presets are caption templates, not code.
- **Stems**: Demucs (`htdemucs_ft`, trained on Western pop) still separated the Hindi track in 49 s; tabla energy lands in `bass`/`drums`, harmonium + sitar in `other`, vocal in `vocals`. Good enough for Vocal-keep remixes. If Indian percussion needs its own stem later, the same tool ships Mel-Band-Roformer models (no new dependency).
- **Time-stretch for Vocal-keep**: the `rubberband` CLI was already installed via Homebrew; `pyrubberband` was added to the stems venv and verified (1.0 s at 92 BPM → 0.74 s at 124 BPM). That was the only missing piece, and it isn't specific to Indian music.
- Everything else (BPM/key detection via librosa, loudness via pyloudnorm, ffmpeg) is already in place. **No new packages.**

## Timing (150 s of audio each, turbo, explicit `bpm` + `vocal_language`)

| Run | What | Wall-clock | Detected BPM (target) |
|---|---|---:|---:|
| `jazzrap-turbo` | jazz-rap: Rhodes, upright bass, brushed drums, muted trumpet, laid-back rap | 31 s | 88 (88) |
| `hindi-roman-turbo` | Bollywood ballad, romanized Hindi, `hi` | 36 s | 89 (92) |
| `hindi-deva-turbo` | same seed, Devanagari lyrics | 30 s | 89 (92) |
| `urdu-roman-turbo` | Pakistani sufi pop, Roman Urdu, `ur` | 30 s | 95 (96) |
| `urdu-script-turbo` | same seed, Nastaliq lyrics | 30 s | 95 (96) |
| `hindi-to-deephouse` | cover, strength 0.5, "Bollywood deep house, tabla over the groove" | 42 s | **125 (124)** |
| `urdu-to-deephouse` | cover, strength 0.5, "sufi deep house, harmonium drone" | 39 s | **125 (122)** |
| `rock-turbo` | alt-rock source, gritty male vocal | 48 s | 128 (128) |
| `rock-to-jazzrap` | cover, strength 0.4 (big genre jump) | 45 s | 88 (88) |
| `rock-to-deephouse` | cover, strength 0.5 | 42 s | 128 (124) — kept the source tempo |
| stems on `hindi-roman-turbo` | htdemucs_ft | 49 s | — |

Engine stayed up for all 11 renders plus the stems run (the stems tool ran only after the engine was idle — the one-GPU-workload rule).

**Two product notes.** (1) With `bpm` passed explicitly every text2music render landed within 3 BPM of target — confirms the Phase 0 decision to send BPM from the Claude brief rather than rely on the caption. (2) `rock-to-deephouse` at strength 0.5 kept the rock's 128 BPM instead of moving to 124: at strength ≥0.5 the source rhythm wins. For a tempo change the preset should use ~0.4, or the Vocal-keep path (stretch the vocal, regenerate the bed at the target tempo). Both rock covers otherwise transformed genre (jazz-rap landed exactly on its 88 BPM half-time feel).

## Listen (in `spike/out/share/`)

1. `jazzrap-turbo_1.mp3` — the new style. *Deep and cool enough?*
2. `hindi-roman-turbo_1.mp3` vs `hindi-deva-turbo_1.mp3` — same seed; *which pronunciation is more natural?* Decides whether the product transliterates or asks for native script.
3. `urdu-roman-turbo_1.mp3` vs `urdu-script-turbo_1.mp3` — same test for Urdu.
4. `hindi-to-deephouse_1.mp3`, `urdu-to-deephouse_1.mp3` — the actual use case (desi deep house / sufi house).
5. `hindi-roman-turbo_1_vocals-stem.mp3` + `_other-stem.mp3` — how clean the vocal and the harmonium/sitar bed come apart.
6. `rock-turbo_1.mp3` → `rock-to-jazzrap_1.mp3` → `rock-to-deephouse_1.mp3` — rock into both layouts.

## Presets this adds to V1

Create: **Jazz-rap / jazz-hop**, **Bollywood ballad**, **Punjabi pop / bhangra**, **Sufi pop / qawwali-inspired**, **Alt-rock** (plus a language picker: English, Hindi, Urdu, Punjabi, Bengali, …, and free text). Remix targets: **Deep house**, **Desi deep house** (tabla layer), **Sufi house** (harmonium drone), **Jazz-rap layout**, plus the originals. Every preset = caption template + default strength + target BPM; all live in one data file, no engine changes.

---

# Phase 0d — a real upload: keep-my-voice remix + lyric extraction

The user's own Urdu song (112 s, ~126 BPM, mastered at −11.6 LUFS) exposed two things the synthetic tests couldn't.

1. **A cover with no lyrics comes back INSTRUMENTAL.** The API's `is_instrumental(lyrics)` treats empty lyrics as "no vocals", so the first three remixes of the upload had music and no voice. Every earlier cover had lyrics attached, which is why it never showed.
2. **`mlx-audio-separator` is broken** — its htdemucs stems were ~35 dB quiet and did not sum back to the mix (residual energy 0.90 of the source), and Whisper on those stems hallucinated "موسیقی" (music) four times. **Meta's reference `demucs` on MPS** separates the same song in 39 s with a residual of 0.018 and a vocal at −16 dB RMS. The stems venv now uses `demucs`; the MLX package stays only as a warning in CLAUDE.md.

**What now works, end to end, on the upload (`spike/run_vocal_keep_user.sh`):**

| Step | Tool | Time |
|---|---|---:|
| Stems (vocals/drums/bass/other) | `demucs htdemucs_ft` on MPS | 39 s |
| Lyrics from the vocal stem | `mlx-whisper` large-v3, `language=ur` | **7 s → 14 lines of real Urdu** |
| Tempo stretch vocal + instrumental (126 → 118 / 108) | `pyrubberband` | ~5 s |
| New bed: ACE-Step **cover of the instrumental only** (no lyrics ⇒ instrumental) | turbo, strength 0.5, explicit `bpm` | 40–54 s |
| Mix the real vocal back over the bed, loudness to −14 LUFS, true-peak safe | `pyloudnorm` | ~2 s |
| **Total per remix** | `spike/vocal_keep.py` | **42–58 s** |

Three variants shipped to the user: emotional deep house at 118, chill at 108, and emotional at the native 126 (no stretch, vocal untouched). Measured tempos 117/108/126, mixes at −14 LUFS, beds structurally aligned with the source instrumental (onset-envelope lag ≈ 0).

**Design consequences (now in the Remix mock):**
- The first choice on the Style step is **Keep my voice / Re-sing it / Instrumental**, defaulting to *Keep my voice* for uploads. "Re-sing" needs lyrics, which the analysis step now extracts automatically (Suno does this too) and shows for correction.
- Lyric transcription is a first-class analysis stage ("Listening for the lyrics"), on the vocal stem, language-aware. Claude then romanizes non-Latin scripts per the user's rule.
- Stem separation, Whisper, and the engine share **one GPU lane**, serialized.

---

# Phase 0e — the direction: **hybrid** (your voice + AI backing), and a command-line front door

The user's verdict on the vocal levers: plain bed-swaps felt like "the same song with new instruments"; the AI re-sing loses the singer; **the hybrid — the real lead vocal placed over an AI cover that includes backing vocals answering it — is the direction.** Four more hybrids were rendered to map the space (more-AI, chill 118, sufi house, afro house), each ≈50 s (cover ~42 s + DSP ~8 s).

How a hybrid is built (`bin/riff remix --mode hybrid`, default):
1. Demucs → vocal stem; Whisper (vocal stem, `--lang`) → lyrics; librosa → tempo.
2. ACE-Step **cover of the full song WITH the transcribed lyrics**, caption asks for "stacked backing vocal harmonies / call-and-response answering the lead", strength ≈0.45, **`bpm` = the song's own tempo** (alignment is exact only at native tempo).
3. `vocal_fx.py`: the real vocal gets doubles, pitch-shifted harmonies (`--harmony 12` default), dotted-eighth delay throws, optional intro chops; the AI cover sits `--bed-under` LU below it (1 LU default; negative pushes the AI vocals forward).
4. Optional `--bpm-to`: stretch the *finished* mix and vocal together (never stretch before the cover — that drifted 2 s).
5. Loudness to −14 LUFS, true-peak safe → WAV + MP3 in `var/out/<name>/`.

**CLI validated end-to-end as the README describes:** `riff create` (2 takes × 60 s jazz-rap) in 28 s; `riff remix` hybrid on the 112 s Urdu upload in 110 s including stems + transcription. The README is the runbook; the web app (Phases 1–4) wraps exactly these commands.

Next for the Remix mock: the "Your voice" choice becomes **Your voice + AI backing** (default) / Your voice only / AI sings it / Instrumental, with an "AI vocals forward ⇄ back" dial (`--bed-under`) and a "Harmonies on my voice" toggle.

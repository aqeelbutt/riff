# Riff

An AI music studio in the spirit of Suno, running entirely on your own Mac. Give it lyrics and a style and it renders a full song with vocals in about 30 seconds. Drop in a song you own and it separates your vocal, extracts the lyrics, and rebuilds the music around your real voice in any style — deep house, sufi house, jazz-rap, rap-rock, afro house, or anything you can describe.

**Status:** Phase 1 complete — the API, the job runner and the music-provider seam are real; `pnpm dev` brings the whole stack up. The Create/Remix/Library screens land in Phases 2–4 — see [`docs/RIFF_V1_PLAN.md`](./docs/RIFF_V1_PLAN.md); the clickable mocks are the [Create flow](https://claude.ai/code/artifact/80a6902e-94c4-4161-9ad3-33faea3e9b4f) and the [Remix flow](https://claude.ai/code/artifact/1071fa9b-0f92-4195-a1b6-1e982845d37f). Spike results and every measured number: [`docs/PHASE0_SPIKE.md`](./docs/PHASE0_SPIKE.md).

---

## 1. Requirements

- Apple Silicon Mac (tested: M4 Pro, 48 GB). 16 GB works with the smaller models; 24 GB+ recommended.
- macOS 14+, [Homebrew](https://brew.sh), and [`uv`](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`).
- ~45 GB free disk for the first install (≈15 GB of music-model weights, ≈3.5 GB of stem/lyric models, plus two Python environments).
- `ffmpeg` and `rubberband` (`brew install ffmpeg rubberband` — `scripts/tools.sh` installs them if missing).

## 2. Install (one time, ~20 minutes, mostly downloads)

```bash
git clone --recurse-submodules git@github.com:aqeelbutt/riff.git
cd riff
scripts/engine.sh install     # the music engine (ACE-Step 1.5): python env + weights → services/ace-step/checkpoints/
scripts/tools.sh install      # stems (Demucs), lyrics (Whisper), tempo stretch, mastering → services/stems/.venv
export PATH="$PWD/bin:$PATH"  # gives you the `riff` command (add to ~/.zshrc to keep it)
```

If you cloned without `--recurse-submodules`, run `git submodule update --init` first.

## 3. Bring the app up

The whole stack (Postgres, migrations, the music engine, the API, the web) with one command:

```bash
pnpm install                  # once — installs turbo + the web app's dependencies
pnpm dev
```

| What | Where |
|---|---|
| Web (status page for now; Create/Remix screens land in Phase 2+) | http://localhost:3000 |
| API (OpenAPI docs at `/docs`) | http://127.0.0.1:8010 |
| Music engine | http://127.0.0.1:8001 |
| Postgres / Redis (docker) | localhost:5433 / localhost:6380 |

Just the engine, for the command line:

```bash
riff engine start             # REST engine on http://127.0.0.1:8001 — ready in ~10 s, loads weights on the first song
riff engine status            # health + loaded models
riff engine stop
```

### Create a song through the API

```bash
curl -s -X POST http://127.0.0.1:8010/songs -H 'Content-Type: application/json' -d '{
  "title": "Needle Talk", "bpm": 92, "duration_s": 150,
  "style": "90s boom-bap hip-hop, hard-knocking dusty drum break, chopped soul samples, vinyl crackle, confident rap vocal",
  "lyrics": "[Verse 1]\nConcrete stairwell, notebook full of scars\n...\n[Hook]\nBoom, bap"}'
curl -s -X POST http://127.0.0.1:8010/songs/<id>/generate -d '{"takes": 2}' -H 'Content-Type: application/json'   # → a job
curl -s http://127.0.0.1:8010/jobs/<job_id>          # poll: queued → rendering → decoding → mastering → done (~1 min)
curl -s http://127.0.0.1:8010/songs/<id>             # generations[] with audio_url / mp3_url
```

`GET /presets` lists every style (Pop, Hip-Hop, **Boom-Bap**, Jazz-Rap, Rap-Rock, Rock, Folk, R&B, Deep House, Lo-fi, Bollywood, Punjabi, Sufi) with its caption and tempo, plus the remix targets — the screens render from it, and you can copy a caption into `--style`.

The engine keeps running in the background; logs are in `var/log/engine.log`. It occasionally dies silently after another GPU-heavy process starts (documented in the spike doc) — `riff` restarts it automatically when you run a command, or run `riff engine start` yourself.

## 4. Create a song

Write lyrics in a text file using section tags (`[Intro]`, `[Verse 1]`, `[Chorus]`, `[Bridge]`, `[Outro]` — add feel to a tag like `[Chorus - anthemic]`), then describe the style:

```bash
riff create --lyrics spike/lyrics/pop.txt \
  --style "upbeat modern pop anthem, driving synth bass, bright guitars, punchy drums, female lead vocal, catchy chorus" \
  --bpm 118 --takes 2
```

You get two takes (different seeds) in about a minute, as WAV + loudness-matched MP3, under `var/out/<name>/`. Open the folder and play them:

```bash
open var/out/pop-*/
```

Options:

| Flag | What it does | Default |
|---|---|---|
| `--style "…"` | the caption: genre, instruments, vocal, mood. Be specific ("muted trumpet", "brushed drums") | required |
| `--bpm N` | tempo — always set it; the style text alone is not honored | model picks |
| `--lang xx` | vocal language: `en`, `hi`, `ur`, `pa`, `bn`, `es`, … Write Hindi/Urdu/Punjabi lyrics **in Roman script** (`tere bina`, not تیرے بنا) — it sounds better | `en` |
| `--length S` | seconds of audio, 10–600 | 150 |
| `--takes N` | variations per run, 1–8 | 2 |
| `--quality studio` | the slower, more detailed model (~3 min per take instead of ~30 s) | `fast` |
| `--name x` | output folder name | from the lyrics filename |

Ready-made lyric files to try: `spike/lyrics/{pop,hiphop,folk,rock,jazzrap,raprock,hindi-roman,urdu-roman}.txt`. Style ideas that are verified to work: *jazz rap with Rhodes and upright bass*, *rap rock mashup with rapped verses and a huge sung chorus*, *romantic Bollywood ballad with sitar and tabla*, *Pakistani sufi pop with harmonium and dholak*, *warm acoustic folk-country*, *modern trap hip-hop*.

## 5. Remix a song you own

```bash
riff remix ~/Music/my-song.mp3 --lang ur \
  --style "emotional deep house, lush stacked backing vocal harmonies answering the lead, ethereal pads, gentle piano, deep sub bass, soft four-on-the-floor, dreamy"
```

What happens (about 2 minutes end to end): the song is split into vocal / drums / bass / other (Demucs), the lyrics are transcribed from your vocal (Whisper, in the language you gave), the tempo is measured, then the engine renders the new version and your real vocal is placed back on top with doubles, harmonies and delay throws, mastered to −14 LUFS. Output: `var/out/<name>/` with the WAV, MP3, and `lyrics.txt` (fix the lyrics and re-run if the transcription missed a line).

Modes (`--mode`):

| Mode | What you get | Your voice? |
|---|---|---|
| `hybrid` *(default)* | your real lead over an AI performance that includes backing vocals answering you | yes + AI backing |
| `keep` | your real lead over a brand-new instrumental only | yes |
| `resing` | the AI sings your transcribed lyrics in the new style | no |
| `instrumental` | music only | no |

Dials:

| Flag | What it does | Default |
|---|---|---|
| `--closeness 0.3–0.8` | how much of the original survives: 0.35 reinvents, 0.45 balanced, 0.65 faithful | 0.45 |
| `--bpm-to N` | change the tempo (stretches your vocal and the new music together) | keep the song's tempo |
| `--harmony 7,12` | harmony intervals stacked on your voice, in semitones (`7` fifth, `12` octave, `3` or `4` thirds) | `12` |
| `--chops` | adds an eighth-note vocal-chop intro from your first phrase | off |
| `--bed-under N` | how far (LU) the music sits under your lead; lower = more AI vocals/music forward | 1 |
| `--lang xx` | language for the transcription and the AI vocals | `en` |

Just want the lyrics out of a song? `riff lyrics ~/Music/my-song.mp3 --lang ur`.

Only remix music you own or have the rights to. Nothing leaves your Mac.

## 6. Where things are

| Path | What |
|---|---|
| `apps/backend/` | FastAPI API: songs · generations · jobs (single GPU lane, retry + reaper) · presets · the `MusicProvider` seam (`services/music/`: ACE-Step + a fake for tests). `./run_tests.sh` |
| `apps/web/` | Next.js 15 app (status page today). `pnpm test` (vitest) · `pnpm build` |
| `bin/riff` | the command-line front door (engine / create / remix / lyrics) |
| `scripts/engine.sh`, `scripts/tools.sh` | install/start/stop for the engine and the audio tools |
| `services/ace-step/` | the music engine, a pinned git submodule (MIT). Weights in `checkpoints/` (gitignored) |
| `services/stems/` | audio-tools Python env: Demucs, Whisper, rubberband, librosa, pyloudnorm |
| `spike/` | the Phase 0 harness the CLI is built on: `run_spike.py` (engine client), `vocal_keep.py`, `vocal_fx.py`, `transcribe.py`, lyric fixtures |
| `var/out/` · `var/media/` | CLI renders · API renders (gitignored) · logs in `var/log/` |
| `docs/` | the plan, the spike results, the mock templates |

## 7. Troubleshooting

- **"engine not responding"** → `riff engine start`, then `tail -f var/log/engine.log`. First start after install takes ~30 s to load weights.
- **A remix came back with no vocals** → you used `--mode instrumental`, or the transcription was empty (check `var/out/<name>/lyrics.txt`; pass the right `--lang`).
- **The beat drifts against the vocal** → don't change tempo by more than ~15%; use `--bpm-to` near the original.
- **Slow renders** → one GPU job at a time. Don't run two `riff` commands, or Demucs/Whisper, while a render is in flight.
- **Out of disk** → weights are 15 GB in `services/ace-step/checkpoints/`; rendered WAVs pile up in `var/out/` and `spike/out/`.

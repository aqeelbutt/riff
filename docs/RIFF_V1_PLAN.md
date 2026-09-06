# Riff — V1 Plan & Roadmap

Working codename: **Riff** (repo `~/code/riff`). Rename is a one-line decision; nothing below depends on it.

An AI music studio in the spirit of Suno: give it a few keywords, it writes complete lyrics with Claude, then renders a full song with vocals in any genre. It can also take an existing song and re-render it as a deep house (or any other style) remix. V1 runs entirely on your Mac. The architecture is shaped so V2 can move to hosted + mobile without a rewrite.

---

## 1. The one decision that shapes everything: the music engine

Claude writes lyrics and style briefs. Claude does **not** generate audio. So V1 needs a separate music model, and the choice constrains cost, quality, latency, and licensing.

| Option | Vocals + lyrics | Remix / cover from audio | Runs on your M4 Pro | License / cost | Verdict |
|---|---|---|---|---|---|
| **ACE-Step 1.5** (open, Jan 2026) | Yes, up to 10 min | Yes (cover, repaint, extend, vocal→BGM) | Yes, native MLX + MPS; 48 GB = top hardware tier | MIT, free | **V1 engine** |
| Suno | Best-in-class | Yes | n/a | No public API (partner-only) | Not available |
| ElevenLabs Music | Yes | Limited (v2 API "coming soon" as of May 2026) | Hosted | ~$0.15/min, commercial-cleared, licensed training data | **V1.5 hosted fallback** |
| YuE 7B | Yes | No | Heavy, slow | Apache 2.0 | No (slow autoregressive) |
| DiffRhythm 2 | Yes | Partial | Yes | Research license | Runner-up; vocals trail ACE-Step |
| MusicGen / Stable Audio Open | Instrumental only | No | Yes | Various | No vocals, out |

**Decision: ACE-Step 1.5 locally, behind a `MusicProvider` interface.** ACE-Step is the only option that covers both product pillars (text→song with vocals, and audio→cover remix) with zero per-song cost and no rights ambiguity in the engine itself. It ships a REST API server (`localhost:8001`) and a Python SDK, so it slots in as a sidecar the way Postgres and Redis do today.

Honest expectation-setting: open models trail Suno v5 on vocal realism. ACE-Step's own benchmarks put it ahead of most commercial alternatives, but the Phase 0 spike below exists to confirm it meets *your* bar before we build a product on it. The provider interface is the insurance policy: if quality disappoints, ElevenLabs Music plugs in without touching the product layer.

Measured Mac performance (community benchmarks, turbo mode, 30-second clip): ~45 s on M1 Pro, ~25 s on M3 Pro; SFT (higher quality) mode ~1.5–3 min. Expect a full 3-minute song on the M4 Pro to take roughly **1–4 minutes** depending on mode. That makes generation an **async job**, not a request.

Sources: [ACE-Step 1.5 repo](https://github.com/ace-step/ACE-Step-1.5), [Apple Silicon port + benchmarks](https://github.com/clockworksquirrel/ace-step-apple-silicon), [Does Suno have an API? (2026)](https://aimusicapi.ai/en/blog/does-suno-have-an-api), [ElevenLabs Music pricing](https://bigvu.tv/blog/elevenlabs-pricing-2026-plans-credits-commercial-rights-api-costs/), [Open-source music gen comparison](https://www.spheron.network/blog/deploy-open-source-ai-music-generation-gpu-cloud-2026/), [MLX stem separation](https://github.com/ssmall256/mlx-audio-separator).

---

## 2. Architecture (mirrors the PursuitAI harness)

```
riff/                          pnpm + turbo monorepo
├── apps/backend/              FastAPI · async SQLAlchemy (asyncpg) · Alembic · own venv
│   └── app/
│       ├── api/               songs · lyrics · remixes · jobs · uploads · settings
│       ├── services/
│       │   ├── lyrics/        Claude: brief → lyrics → section regenerate
│       │   ├── music/         MusicProvider interface + ACEStepProvider + FakeProvider (tests)
│       │   ├── remix/         stem separation · tempo/key analysis · cover pipeline · mixdown
│       │   ├── jobs.py        enqueue → claim (FOR UPDATE SKIP LOCKED) → run · heartbeat · progress
│       │   └── storage.py     StorageProvider: LocalFS (V1) → S3 (V2)
│       └── models/            users · songs · generations · uploads · stems · remixes · jobs · ai_call_telemetry
├── apps/web/                  Next.js 15 · Tailwind · vitest + RTL · Playwright
├── apps/mobile/               (V2) Expo — reserved, not scaffolded in V1
├── services/ace-step/         ACE-Step 1.5 sidecar: pinned checkout, own uv venv, start script → :8001
├── docker-compose.yml         postgres · redis
├── changelog.d/               fragments, assembled at release
├── docs/                      this plan · ENGINE_RUNBOOK.md · MOBILE_PARITY_BACKLOG.md (V2)
└── CLAUDE.md                  harness rules carried over
```

Harness rules carried over verbatim: feature branch → `develop`, squash; `develop → main` merge commit; changelog fragments not direct edits; `.env.example` parity for every setting; every web UI change ships a vitest test; clickable mock before any screen; modules that open their own DB session get a conftest redirect fixture; charge-after-validation for every Claude call; `_i()` inline SVG icons, no Lucide barrel imports; theme tokens, no hardcoded colors.

### Two pipelines

**Create (keywords → song)**
1. User enters keywords + picks genre/mood chips (or free text) — presets include Pop, Hip-Hop, **Jazz-Rap**, Folk, Rock, **Bollywood ballad**, **Punjabi pop/bhangra**, **Sufi pop**. A **vocal language** picker (English, Hindi, Urdu, Punjabi, Bengali, … — passed to the engine as `vocal_language`; lyrics in romanized or native script both work). Optional: title, explicit/clean, duration target, instrumental-only.
2. `POST /lyrics/brief` — Claude turns keywords into a **Song Brief** (structured output): title options, genre, sub-genre, BPM range, key suggestion, mood, instrumentation, vocal style, song structure. Cheap, fast, editable.
3. `POST /lyrics/write` — Claude writes full lyrics against the brief, emitting ACE-Step section tags (`[Intro] [Verse 1] [Pre-Chorus] [Chorus] [Bridge] [Outro]`). Each section is regenerable on its own (`POST /lyrics/regenerate-section`).
4. `POST /songs/{id}/generate` — enqueues a job: brief + lyrics → ACE-Step caption/tags + lyrics → `POST /release_task` on the sidecar → poll `/query_result` → WAV → normalize → store → `generations` row. Produces **2 variations per run** (Suno convention) via different seeds.
5. Web polls `GET /jobs/{id}` (mirrors `useAiJob`: persists in-flight id per song, re-attaches on reload, pauses when tab hidden). Staged progress: queued → planning → rendering → mastering → done.

**Remix (existing song → new style)**
1. User uploads an MP3/WAV/M4A they have rights to (rights checkbox recorded on the `uploads` row).
2. Analysis job: stem separation via Demucs (MLX port on Mac, ~seconds), BPM + key via `librosa`, duration, loudness. Stems are stored and previewable (vocals / drums / bass / other).
3. User picks a **style preset** (Deep House, Desi Deep House, Sufi House, Jazz-Rap layout, Tech House, Lo-fi Hip-Hop, Synthwave, Drum & Bass, Acoustic, Orchestral, Reggaeton, Phonk, Afrobeats…) or writes a free style prompt. Each preset is a caption template + default cover strength + target BPM + structure hints; Deep House = 120–126 BPM, four-on-the-floor, sidechained pads, filtered chords. Any source genre works (rock → jazz-rap and rock → deep house verified in Phase 0c); a big genre jump uses strength ~0.4, a tempo change ≥0.5 keeps the source rhythm.
4. Two remix modes, both via ACE-Step reference-audio input:
   - **Cover** (default, simplest): ACE-Step cover mode with the original as reference + the new style caption. Keeps melody/lyrics, re-renders everything.
   - **Vocal-keep**: regenerate only the accompaniment in the new style, time-stretch the isolated original vocal to the target BPM (`pyrubberband`), re-layer, mixdown + loudness-normalize (`pyloudnorm`). Higher fidelity to the original singer, more moving parts.
5. Same job/progress/variations flow as Create.

### Job model
Generation is 1–4 minutes locally, so everything is a `jobs` row with a single in-process worker (asyncio task, DB-claimed, heartbeat, `progress` JSON with real stage labels the client renders dumbly). Same shape as PursuitAI's `ai_jobs`, minus the multi-machine lease (single Mac). Idempotency key dedupes double-clicks. A reaper re-queues jobs whose worker died and fails past `MAX_ATTEMPTS`.

### Claude usage
- Model: `claude-opus-5`, adaptive thinking, structured outputs for the brief, streaming for lyrics so the editor fills in live.
- One `call_claude_with_retry` wrapper with telemetry (`ai_call_telemetry` + `ai_call_events`), copied from PursuitAI. Every call records tokens + USD so the Settings page shows "this month's Claude spend".
- Prompt-cache the stable system prompt (genre glossary + lyric craft rules + section-tag spec).
- Guardrails in the system prompt: no reproducing existing copyrighted lyrics, no named-artist impersonation ("in the style of X" → describe the traits, never the name in the ACE-Step caption).

### Data model (V1)
`users` (single local user seeded; `user_id` on every row so multi-tenant later is a migration, not a rewrite) · `songs` (title, keywords, brief JSON, lyrics text, style caption, status) · `generations` (song_id, provider, params JSON, seed, duration_s, file_path, loudness, is_favorite) · `uploads` (source audio, rights_confirmed_at, analysis JSON) · `stems` (upload_id, kind, file_path) · `remixes` (upload_id, mode, preset, caption, target_bpm → generations) · `jobs` · `ai_call_telemetry` · `ai_call_events`.

### Web surfaces (mock-first, each gated on a clickable prototype)
1. **Create** — keyword field + genre/mood chips + "Write lyrics" → split view: brief card (editable) | lyrics editor with per-section regenerate → Generate.
2. **Library** — grid of songs with cover art placeholder, status chips, favorites; persistent bottom player bar (play/pause, scrub, waveform, A/B between variations).
3. **Song detail** — waveform player, lyrics, variations, download WAV/MP3, "Remix this", "Extend".
4. **Remix** — upload dropzone → analysis card (BPM, key, stems preview) → style preset grid → mode toggle → Generate.
5. **Settings** — Anthropic key status, engine status (sidecar up? model tier? last generation time), storage usage, Claude spend.

---

## 3. V1 scope

**In**
- Keywords → Claude brief → Claude lyrics (with section regenerate) → ACE-Step full song with vocals, 2 variations, any genre via presets + free text; instrumental-only toggle.
- Remix: upload → stems + analysis → style preset → Cover mode. Vocal-keep mode if Phase 0 proves it.
- Library + player + download (WAV + MP3).
- Async jobs with real staged progress, retry, reap.
- Claude cost telemetry; engine health on Settings.
- Backend pytest suite (FakeProvider, no model in CI), web vitest suite, one Playwright E2E per pipeline against the fake provider, plus one real end-to-end run on the Mac documented with numbers.

**Out (V2+)**
- Accounts, auth, billing, tiers (PursuitAI's auth/Stripe stack ports over when needed).
- Hosted deployment (Fly), hosted music provider (ElevenLabs), S3 storage.
- Mobile (Expo) — reserved directory + parity backlog doc only.
- Voice cloning, extend/inpaint UI, stem export as a feature, sharing/public pages, cover-art generation, MIDI export.

---

## 4. Roadmap

| Phase | Goal | Exit criteria | Est. |
|---|---|---|---|
| **0 · Engine spike** | Prove ACE-Step on this Mac before building on it | ACE-Step 1.5 running from `services/ace-step/` with pinned commit; 3 genres × turbo/SFT/XL timed; cover mode tried on 2 tracks (one → deep house); Demucs MLX stems on the same tracks; a written go/no-go with WAVs you've listened to | 3–4 days |
| **1 · Scaffold + generation spine** | Monorepo, DB, jobs, provider, first song via API | `pnpm dev` brings up postgres/redis/backend/web/sidecar; `POST /songs` + `/generate` → job → WAV on disk; FakeProvider in tests; conftest redirects; `.env.example` complete | 1 week |
| **2 · Lyrics + Create flow** | Claude brief + lyrics, first real screen | Mock signed off → Create page live; streaming lyrics; per-section regenerate; structured brief; telemetry rows; vitest for the hook + editor logic | 1 week |
| **3 · Library + player** | Listen, compare, keep | Library grid, song detail, persistent player, A/B variations, favorites, download; Playwright E2E for Create→play | 1 week |
| **4 · Remix** | Upload → stems → styled cover | Remix page, analysis job, preset grid, Cover mode end-to-end; Vocal-keep behind a flag if Phase 0 said yes | 1.5 weeks |
| **5 · Harden + release 1.0.0** | Make it a real 1.0 | Reaper + idempotency tests; error states designed; engine runbook; CLAUDE.md for the repo; changelog assembled; tag `v1.0.0` | 3–4 days |

Roughly **6 weeks** of focused work to a V1 you'd use daily. Phase 0 is deliberately first and deliberately cheap: it is the only phase whose outcome can change the plan.

---

## 5. Risks and how the plan handles them

- **Open-model vocal quality below expectations** → Phase 0 listening test before any product code; `MusicProvider` seam keeps ElevenLabs a config change away.
- **Generation latency on a laptop** → async jobs, honest staged progress, turbo mode default with SFT/XL as a "higher quality, slower" toggle.
- **Dependency hell (PyTorch/MLX vs FastAPI venv)** → sidecar has its own `uv` venv and pinned commit; backend only speaks HTTP to it.
- **Remix rights** → V1 is local and personal; still records a rights confirmation per upload and never lets the caption name a real artist, so the V2 hosted version inherits a clean posture.
- **ACE-Step API drift** (young project, moving fast) → pin the commit, wrap it in one adapter, contract-test the adapter against the fake.
- **Claude cost creep** → per-call telemetry from day one, spend visible in Settings, prompt caching on the stable prefix.

---

## 6. Decisions I made on your behalf (override any of them)

1. **Working name** Riff, repo at `~/code/riff`. Separate repo, not a PursuitAI app.
2. **Engine** ACE-Step 1.5 local via sidecar; ElevenLabs Music as the first hosted provider in V1.5.
3. **No auth in V1**, but a `users` table and `user_id` on every row from the first migration.
4. **Remix ships Cover mode first**; Vocal-keep is flag-gated pending the spike.
5. **Lyrics model** `claude-opus-5` with adaptive thinking; Haiku 4.5 nowhere in V1 (quality is the product).
6. **Two variations per generation**, matching the Suno mental model users already have.

## 7. Next step

Phase 0. I'll install ACE-Step 1.5 under `services/ace-step/` on this Mac, run the timing matrix and the deep-house cover test, and hand you the WAVs plus a go/no-go note. After that, the Create-flow clickable mock, per the mock-first gate.

---

## Phase 0 outcome (2026-09-06)

Engineering GO — see [`PHASE0_SPIKE.md`](./PHASE0_SPIKE.md). ACE-Step 1.5 renders a 150-second song with vocals in ~30 s on the M4 Pro (turbo), two takes in ~1 min, SFT in 3 min; deep-house covers re-tempo correctly to the target BPM; Demucs stems in ~50 s. Two plan corrections: (1) the 5Hz LM is off the critical path — the backend passes BPM/key from the Claude brief explicitly (the caption alone is not honored); (2) the sidecar can die silently (2 crashes in the first 2 renders, 0 in the next 16) so it is supervised and jobs are retryable. A loudness-normalization mastering step is added to the render pipeline. The quality verdict awaits your listening pass on `spike/out/share/`.

## Phase 1 outcome (2026-09-06)

**Done, validated live.** `pnpm dev` brings up Postgres (5433) → migrations → the engine → the API (8010) → the web (3000). The spine — `POST /songs` → `POST /songs/{id}/generate` → single-lane DB job (SKIP LOCKED claim, heartbeat, staged progress, retry ×3, reaper, idempotent on content) → `MusicProvider` (ACE-Step) → ffmpeg mastering to −14 LUFS → `Generation` rows → `GET /generations/{id}/mp3` — rendered a real 150 s boom-bap song with two takes in **66 s** end to end. 18 backend tests run against a `FakeProvider` (no engine in CI); 4 web tests; `next build` green. Style presets live in `app/services/presets.py` and are served at `GET /presets` (Boom-Bap added at the user's request, on both Create and Remix). Deferred to Phase 2+: the Create screen (mock approved), Claude brief/lyrics, the remix job kinds (`analyze`, `remix` — the CLI's hybrid pipeline becomes handlers).

## Phase 2 outcome (2026-09-06)

**Done, validated live in the browser.** The Create screen is the approved mock, wired end to end: keywords + style/mood/voice/language → `POST /lyrics/brief` (Claude `claude-opus-5`, strict structured output — titles, engine caption, BPM, key, mood, structure; ~8 s) → `POST /lyrics/write` streamed over SSE into the section editor (~17 s for a full song) → per-section Rewrite / Shorter / Remove / inline edit (`POST /lyrics/section`, ~5 s) → Generate → the Phase 1 job spine → two takes with decoded waveforms, play/A-B, keep, download (56 s render). Every Claude call writes an `ai_call_telemetry` row with tokens + USD (a brief ≈ $0.01, lyrics ≈ $0.03; cached system prompts hit on repeat). The job hook persists the in-flight job per song so a reload re-attaches. Backend 28 tests (fake lyrics + fake music provider), web 13 tests, build green. Prompts enforce Roman script for hi/ur/pa/bn and forbid artist names. Deferred: Library (Phase 3), Remix screen + job kinds (Phase 4), the lyrics-sync display.

## Phase 3 outcome (2026-09-06)

**Done, validated live + by E2E.** Library grid (search over title/style/lyrics/keywords, Kept/Ready/Rendering filters, sort, deterministic cover gradients, hover-play) and the song page (takes grouped by run with waveforms, keep/remove/download, rename in place, "2 more takes" via the job hook, delete through a themed confirm; rendering songs refresh on their own). One app-wide player (`PlayerProvider` in the root layout) with A/B between takes that survives navigation; Create now uses it too. Backend: `GET /songs?q=&status=&kept=`, `DELETE /songs/{id}` (removes the media folder), `DELETE /generations/{id}`; 31 tests. Web: 20 unit tests + a Playwright E2E (Create → lyrics → rewrite → render → play → Library → search → song page → keep → delete) that runs in ~6 s against fake providers on its own ports/DB/dist dir. UX fixes from the user's screenshot: the compose column collapses to a rail and widens (persisted), and the Voice control has its own full-width row so no labels overlap. Mock: docs/mocks/library.template.html.

## Phase 4 outcome (2026-09-06)

**Done, validated live on the user's own Urdu song + by E2E.** Backend: `uploads`/`stems`/`remixes` tables; an audio-tools seam (`RealAudioTools` = subprocess into the tools venv: reference Demucs on MPS, mlx-whisper on the vocal stem, librosa tempo/key, the vocal mix; `FakeAudioTools` for tests/E2E); `MusicProvider.cover()`; `analyze` + `remix` job kinds with staged progress; `POST /uploads` (multipart, rights required, ffmpeg-normalized), `/uploads/from-generation/{gen}` (remix your own take, lyrics carried over), `PATCH` lyrics/language, stem streaming, `/uploads/{id}/remix`, `/remixes…`. 40 backend tests. Web: the Remix screen from mock v2 (pure `remixFlow` reducer + hook + page), `/remix?upload=` deep links, Remix buttons on Create/Library; 26 unit tests; a second Playwright journey (upload → check → style → render → A/B → keep) on fake tools. **Two user asks landed mid-phase:** auto-tune ON by default (per-note, formant-preserving Rubber Band, 85 %) and two variations per run; ports moved (web 3010) to coexist with PursuitAI. **One correction from listening:** the first auto-tune sample "collided" — stacked harmonies + the AI cover's own lead + the real lead. Fix: the real vocal is the clean lead, harmonies/doubles off by default, and hybrid now SEPARATES the AI cover (Demucs) and DUCKS its vocals 12 dB under the lead's envelope. Live numbers: analysis 57 s; hybrid remix 2 variations 171 s (cover ≈50 s + cover separation ≈25 s + auto-tune mix ≈10 s each). Remaining: Phase 5.

## Reimagine (2026-09-06, after Phase 4)

The user's verdict on every beat-driven remix: "still pretty horrible … we need to make songs more melodic … hear/understand the song and enhance instead of shoving it into a beat." That is a product insight, not a tuning problem — a cover forces an existing performance into a groove. **Reimagine** inverts it: Claude reads the transcribed lyrics (plus the measured key and tempo), works out the meaning, which repeated lines are the chorus and where the dynamics should lift, and writes a full arrangement in the song's own key; the engine then PERFORMS that arrangement with the same words. Proven on the user's Urdu song before any UI work: two directions (76 BPM ballad, 122 BPM cinematic anthem), briefs in 24 s, two takes each in ~70 s, plus a loose cover that keeps a memory of the original melody. Shipped as the default approach on the Remix screen with six directions, a "Let it be sung / Keep my voice" choice (the latter renders the arrangement instrumental at the original tempo so the real auto-tuned vocal lines up), and Claude's reading shown with the result. 45 backend tests, 29 web tests, 2 E2E journeys.

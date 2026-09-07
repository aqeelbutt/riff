/** Remix flow state machine — pure reducer, unit-tested. Phases: start → analyzing → check → style → rendering → result. */
/** The top-level choice: understand-and-re-perform, or put the recording over a new beat. */
export const APPROACHES = [
  ["reimagine", "Reimagine", "Claude reads your song — meaning, chorus, arc — and writes a new arrangement in your key. The engine performs it."],
  ["restyle", "Restyle", "Put your recording over a new beat, keeping your voice."],
];
export const REIMAGINE_VOICES = [
  ["ai", "Let it be sung", "a new performance of your words — the most melodic result"],
  ["mine", "Keep my voice", "the arrangement is played at your tempo and your auto-tuned vocal sits on top"],
];

export const MODES = [
  ["hybrid", "Your voice + AI backing", "your lead, AI harmonies answering you"],
  ["keep", "Your voice only", "your lead, new music under it"],
  ["resing", "AI sings it", "your lyrics, a new voice"],
  ["instrumental", "Instrumental", "no vocals"],
];

export const initialState = {
  phase: "start",
  upload: null,        // the server's upload record (facts, stems, lyrics, remixes)
  job: null,
  style: { approach: "reimagine", direction: "ballad", reimagineVoice: "ai",
           preset: "deephouse", custom: "", mode: "hybrid", closeness: 50, tempo: "match", bpmCustom: "", aiForward: 1, harmony: false, chops: false,
           autotune: true, autotuneStrength: 85, takes: 2, quality: "fast", moods: ["Emotional", "Chill"] },
  batch: [],           // remixes from the latest run
  error: null,
};

export function reduce(state, action) {
  switch (action.type) {
    case "uploading": return { ...state, phase: "analyzing", upload: null, job: null, batch: [], error: null };
    case "upload_created": return { ...state, phase: "analyzing", upload: action.upload, job: action.job };
    case "job_update": return { ...state, job: action.job };
    case "analyzed": return { ...state, phase: "check", upload: action.upload, job: null, style: { ...state.style, tempo: "match" } };
    case "analysis_failed": return { ...state, phase: "start", error: action.error, job: null };
    case "upload_patch": return { ...state, upload: { ...state.upload, ...action.patch } };
    case "to_style": return { ...state, phase: "style", error: null };
    case "to_check": return { ...state, phase: "check", error: null };
    case "style": return { ...state, style: { ...state.style, ...action.patch } };
    case "start_render": return { ...state, phase: "rendering", job: action.job, batch: action.remixes, error: null };
    case "render_done": return { ...state, phase: "result", job: action.job, upload: action.upload, batch: action.batch };
    case "render_failed": return { ...state, phase: "style", job: action.job, error: action.error };
    case "open_result": return { ...state, phase: "result", upload: action.upload, batch: action.batch, job: null };
    case "reset": return { ...initialState, style: state.style };
    case "error": return { ...state, error: action.error };
    default: return state;
  }
}

export const closenessLabel = (v) => v <= 35 ? "Reinvented — a new song that remembers yours" : v <= 45 ? "Loose — the melody survives, the rest is new"
  : v <= 55 ? "Balanced — recognizable, clearly transformed" : v <= 65 ? "Close — same feel, new instruments" : "Faithful — subtle restyle";
export const aiLabel = (v) => v <= -2 ? "Way back — a whisper of AI harmonies" : v <= 0 ? "Behind you — subtle backing"
  : v <= 1 ? "Balanced — the AI answers you, you stay in front" : v <= 2 ? "Forward — a real duet" : "Front — the AI leads, you ride on top";

/** Target tempo for the run: keep the song's, match the preset's, or a custom number. */
export function targetBpm(style, upload, presets) {
  if (style.tempo === "keep") return null;
  if (style.tempo === "custom") { const n = Number(style.bpmCustom); return n >= 40 && n <= 220 ? n : null; }
  const p = (presets || []).find((x) => x.key === style.preset);
  return p && p.bpm ? p.bpm : null;
}

export const isReimagine = (style) => style.approach === "reimagine";
/** The API mode for the current choices. */
export function modeOf(style) {
  if (!isReimagine(style)) return style.mode;
  return style.reimagineVoice === "mine" ? "reimagine_keep" : "reimagine";
}

/** Engine quality. Fast is the turbo model at 8 inference steps; studio is the SFT model at 50 — roughly six
 *  times slower and audibly more detailed in the top end, which is most of what separates a render from a record. */
export const QUALITIES = [
  ["fast", "Fast", "turbo · seconds · for auditioning"],
  ["studio", "Studio", "50 steps · ~6x slower · more detail"],
];

/** POST /uploads/{id}/remix body from the style state. */
export function remixBody(style, upload, presets, reimaginePresets) {
  if (isReimagine(style)) {
    const d = (reimaginePresets || []).find((x) => x.key === style.direction);
    return {
      mode: modeOf(style),
      preset_key: style.direction === "custom" ? null : style.direction,
      style: style.direction === "custom" ? style.custom.trim() || null : null,
      direction: style.direction === "custom" ? style.custom.trim().slice(0, 120) : (d?.label || style.direction),
      autotune: !!style.autotune,
      autotune_strength: Math.round(style.autotuneStrength) / 100,
      harmony: style.harmony ? "12" : "",
      chops: !!style.chops,
      takes: style.takes,
      quality: style.quality || "fast",
      moods: style.moods,
    };
  }
  return restyleBody(style, upload, presets);
}

function restyleBody(style, upload, presets) {
  const bpmTo = targetBpm(style, upload, presets);
  return {
    preset_key: style.preset === "custom" ? null : style.preset,
    style: style.preset === "custom" ? style.custom.trim() || null : null,
    mode: style.mode,
    closeness: Math.round(style.closeness) / 100,
    bpm_to: bpmTo && upload?.bpm && Math.abs(bpmTo - upload.bpm) > 0.5 ? bpmTo : null,
    ai_forward: style.aiForward,
    harmony: style.harmony ? "12" : "",
    chops: !!style.chops,
    autotune: !!style.autotune,
    autotune_strength: Math.round(style.autotuneStrength) / 100,
    takes: style.takes,
    quality: style.quality || "fast",
    moods: style.moods,
  };
}

export const canRemix = (s) => {
  if (s.phase !== "style" || !s.upload) return false;
  if (isReimagine(s.style)) {
    if (!(s.upload.lyrics || "").trim()) return false; // reimagine needs words to understand
    return s.style.direction !== "custom" || s.style.custom.trim().length > 3;
  }
  return s.style.preset !== "custom" || s.style.custom.trim().length > 3;
};
export const showsVoiceOpts = (mode) => mode === "hybrid" || mode === "keep";

/** Stage rows for a remix job (backend owns labels). */
export function stageRows(job) {
  const stages = job?.progress?.stages || [];
  const cur = job?.progress?.current || "queued";
  const idx = stages.findIndex((s) => s.key === cur);
  return stages.map((s, i) => ({ ...s, state: cur === "done" || i < idx ? "done" : i === idx ? "current" : "todo" }));
}

export const summary = (s, presets, reimaginePresets) => {
  if (isReimagine(s.style)) {
    const d = (reimaginePresets || []).find((x) => x.key === s.style.direction);
    const name = s.style.direction === "custom" ? (s.style.custom.trim() || "Custom") : (d?.label || s.style.direction);
    const voice = s.style.reimagineVoice === "mine" ? "your voice on it" : "newly sung";
    return [`Reimagined · ${name}`, voice, s.upload?.key && `in ${s.upload.key}`, s.style.autotune && s.style.reimagineVoice === "mine" && "auto-tune",
      `${s.style.takes} variation${s.style.takes === 1 ? "" : "s"}`, s.style.quality === "studio" && "studio"].filter(Boolean).join(" · ");
  }
  const p = (presets || []).find((x) => x.key === s.style.preset);
  const name = s.style.preset === "custom" ? (s.style.custom.trim() || "Custom") : (p?.label || s.style.preset);
  const mode = MODES.find((m) => m[0] === s.style.mode)?.[1].toLowerCase();
  const bpm = targetBpm(s.style, s.upload, presets) || (s.upload?.bpm ? Math.round(s.upload.bpm) : null);
  return [name, mode, closenessLabel(s.style.closeness).split(" —")[0].toLowerCase(), bpm && `${bpm} BPM`, s.style.autotune && "auto-tune", `${s.style.takes} variation${s.style.takes === 1 ? "" : "s"}`, s.style.quality === "studio" && "studio"].filter(Boolean).join(" · ");
};

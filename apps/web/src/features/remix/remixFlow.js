/** Remix flow state machine — pure reducer, unit-tested. Phases: start → analyzing → check → style → rendering → result. */
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
  style: { preset: "deephouse", custom: "", mode: "hybrid", closeness: 50, tempo: "match", bpmCustom: "", aiForward: 1, harmony: false, chops: false,
           autotune: true, autotuneStrength: 85, takes: 2, moods: ["Emotional", "Chill"] },
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

/** POST /uploads/{id}/remix body from the style state. */
export function remixBody(style, upload, presets) {
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
    moods: style.moods,
  };
}

export const canRemix = (s) => s.phase === "style" && !!s.upload && (s.style.preset !== "custom" || s.style.custom.trim().length > 3);
export const showsVoiceOpts = (mode) => mode === "hybrid" || mode === "keep";

/** Stage rows for a remix job (backend owns labels). */
export function stageRows(job) {
  const stages = job?.progress?.stages || [];
  const cur = job?.progress?.current || "queued";
  const idx = stages.findIndex((s) => s.key === cur);
  return stages.map((s, i) => ({ ...s, state: cur === "done" || i < idx ? "done" : i === idx ? "current" : "todo" }));
}

export const summary = (s, presets) => {
  const p = (presets || []).find((x) => x.key === s.style.preset);
  const name = s.style.preset === "custom" ? (s.style.custom.trim() || "Custom") : (p?.label || s.style.preset);
  const mode = MODES.find((m) => m[0] === s.style.mode)?.[1].toLowerCase();
  const bpm = targetBpm(s.style, s.upload, presets) || (s.upload?.bpm ? Math.round(s.upload.bpm) : null);
  return [name, mode, closenessLabel(s.style.closeness).split(" —")[0].toLowerCase(), bpm && `${bpm} BPM`, s.style.autotune && "auto-tune", `${s.style.takes} variation${s.style.takes === 1 ? "" : "s"}`].filter(Boolean).join(" · ");
};

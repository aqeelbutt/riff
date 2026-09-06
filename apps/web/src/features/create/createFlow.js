/** The Create flow's state machine — a pure reducer, unit-tested; the hook wraps it with the API calls. */
export const PHASES = ["compose", "briefing", "writing", "ready", "rendering", "result"];

export const initialState = {
  phase: "compose",
  compose: { keywords: "", style: null, moods: ["Euphoric"], vocal: "female", language: "en", duration_s: 150, quality: "fast", takes: 2 },
  brief: null,
  engineCaption: "",
  titleIndex: 0,
  lyricsText: "",       // streamed text (authoritative while writing)
  sections: [],         // parsed/edited sections (authoritative once ready)
  busySections: {},     // {index: true} while a rewrite is in flight
  song: null,           // the persisted song (after generate)
  job: null,
  takes: [],
  error: null,
};

export function reduce(state, action) {
  switch (action.type) {
    case "compose": return { ...state, compose: { ...state.compose, ...action.patch }, error: null };
    case "start_brief": return { ...state, phase: "briefing", brief: null, sections: [], lyricsText: "", takes: [], song: null, job: null, error: null };
    case "brief_ready": return { ...state, phase: "writing", brief: action.brief, engineCaption: action.engineCaption, titleIndex: 0, lyricsText: "" };
    case "brief_patch": return { ...state, brief: { ...state.brief, ...action.patch } };
    case "pick_title": return { ...state, titleIndex: action.index };
    case "lyrics_delta": return { ...state, lyricsText: state.lyricsText + action.text };
    case "lyrics_done": return { ...state, phase: "ready", lyricsText: action.lyrics, sections: action.sections };
    case "sections_set": return { ...state, sections: action.sections };
    case "section_busy": return { ...state, busySections: { ...state.busySections, [action.index]: action.busy } };
    case "start_render": return { ...state, phase: "rendering", song: action.song, job: action.job, takes: [], error: null };
    case "job_update": return { ...state, job: action.job };
    case "render_done": return { ...state, phase: "result", job: action.job, song: action.song, takes: action.takes };
    case "render_failed": return { ...state, phase: "ready", job: action.job, error: action.error };
    case "back_to_lyrics": return { ...state, phase: "ready", error: null };
    case "reset": return { ...initialState, compose: { ...initialState.compose, keywords: state.compose.keywords, style: state.compose.style } };
    case "error": return { ...state, error: action.error, phase: action.phase || state.phase };
    default: return state;
  }
}

export const canWrite = (s) => s.compose.keywords.trim().length >= 3 && !["briefing", "writing", "rendering"].includes(s.phase);
export const canGenerate = (s) => s.phase === "ready" && s.sections.length > 0;
export const currentTitle = (s) => s.brief?.titles?.[s.titleIndex] || s.brief?.titles?.[0] || "Untitled";

/** What the UI shows for a render job's progress; the backend owns the labels. */
export function stageRows(job) {
  const stages = job?.progress?.stages || [];
  const cur = job?.progress?.current || "queued";
  const idx = stages.findIndex((s) => s.key === cur);
  return stages.map((s, i) => ({ ...s, state: cur === "done" || i < idx ? "done" : i === idx ? "current" : "todo" }));
}

/** Build the POST /songs body from the flow state. */
export function songBody(s) {
  const b = s.brief;
  return {
    title: currentTitle(s), keywords: s.compose.keywords, style: s.engineCaption || b.style_caption,
    lyrics: s.compose.vocal === "instrumental" ? "" : serialize(s.sections),
    bpm: b.bpm, key: b.key, vocal_language: b.vocal_language || s.compose.language, duration_s: b.duration_s || s.compose.duration_s,
  };
}

function serialize(sections) {
  return sections.filter((x) => x.tag).map((x) => `[${x.tag}]\n${x.lines.join("\n")}`).join("\n\n") + "\n";
}

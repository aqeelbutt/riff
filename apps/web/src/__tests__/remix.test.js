import { describe, expect, it } from "vitest";
import { canRemix, initialState, isReimagine, modeOf, reduce, remixBody, stageRows, summary, targetBpm } from "@/features/remix/remixFlow";

const PRESETS = [{ key: "deephouse", label: "Deep House", bpm: 124 }, { key: "acoustic", label: "Acoustic", bpm: 0 }];
const REIMAGINE = [{ key: "ballad", label: "Emotional ballad", bpm: 76 }, { key: "anthem", label: "Cinematic anthem", bpm: 122 }];
const RESTYLE = { ...initialState.style, approach: "restyle" };
const UPLOAD = { id: "u1", bpm: 126, key: "G major", status: "analyzed", stems: [], lyrics: "la" };

describe("remixFlow reducer", () => {
  it("walks start → analyzing → check → style → rendering → result", () => {
    let s = reduce(initialState, { type: "upload_created", upload: { id: "u1", status: "analyzing" }, job: { id: "j1" } });
    expect(s.phase).toBe("analyzing");
    s = reduce(s, { type: "analyzed", upload: UPLOAD }); expect(s.phase).toBe("check");
    s = reduce(s, { type: "to_style" }); expect(canRemix(s)).toBe(true);
    s = reduce(s, { type: "style", patch: { approach: "restyle", preset: "custom", custom: "" } }); expect(canRemix(s)).toBe(false);
    s = reduce(s, { type: "style", patch: { custom: "sufi house with harmonium" } }); expect(canRemix(s)).toBe(true);
    s = reduce(s, { type: "start_render", job: { id: "j2" }, remixes: [{ id: "r1" }, { id: "r2" }] }); expect(s.phase).toBe("rendering");
    s = reduce(s, { type: "render_done", job: { status: "done" }, upload: UPLOAD, batch: [{ id: "r1", status: "ready" }] });
    expect(s.phase).toBe("result"); expect(s.batch).toHaveLength(1);
    s = reduce(s, { type: "render_failed", job: { status: "failed" }, error: "engine died" });
    expect(s.phase).toBe("style"); expect(s.error).toBe("engine died");
  });
  it("defaults: reimagine (sung), auto-tune on at 85%, two variations", () => {
    expect(initialState.style).toMatchObject({ approach: "reimagine", direction: "ballad", reimagineVoice: "ai", mode: "hybrid", autotune: true, autotuneStrength: 85, takes: 2, harmony: false });
    expect(isReimagine(initialState.style)).toBe(true);
    expect(modeOf(initialState.style)).toBe("reimagine");
    expect(modeOf({ ...initialState.style, reimagineVoice: "mine" })).toBe("reimagine_keep");
    expect(modeOf(RESTYLE)).toBe("hybrid");
  });
});

describe("remixBody · reimagine", () => {
  it("sends the direction and the derived mode, and needs lyrics", () => {
    const body = remixBody(initialState.style, UPLOAD, PRESETS, REIMAGINE);
    expect(body).toMatchObject({ mode: "reimagine", preset_key: "ballad", direction: "Emotional ballad", autotune: true, takes: 2 });
    expect(body.closeness).toBeUndefined(); // closeness/tempo are restyle-only knobs
    const mine = remixBody({ ...initialState.style, reimagineVoice: "mine", direction: "anthem" }, UPLOAD, PRESETS, REIMAGINE);
    expect(mine).toMatchObject({ mode: "reimagine_keep", preset_key: "anthem", direction: "Cinematic anthem" });
    const custom = remixBody({ ...initialState.style, direction: "custom", custom: "  slow qawwali with strings  " }, UPLOAD, PRESETS, REIMAGINE);
    expect(custom).toMatchObject({ preset_key: null, style: "slow qawwali with strings", direction: "slow qawwali with strings" });
  });
  it("blocks when the song has no words to understand", () => {
    const s = { phase: "style", upload: { ...UPLOAD, lyrics: "" }, style: initialState.style };
    expect(canRemix(s)).toBe(false);
    expect(canRemix({ ...s, upload: UPLOAD })).toBe(true);
  });
  it("summarizes the reimagine run", () => {
    expect(summary({ ...initialState, upload: UPLOAD }, PRESETS, REIMAGINE)).toBe("Reimagined · Emotional ballad · newly sung · in G major · 2 variations");
  });
});

describe("remixBody · restyle", () => {
  it("maps the style state to the API contract, omitting a no-op tempo change", () => {
    const body = remixBody(RESTYLE, UPLOAD, PRESETS);
    expect(body).toMatchObject({ preset_key: "deephouse", style: null, mode: "hybrid", closeness: 0.5, ai_forward: 1, harmony: "", chops: false, autotune: true, autotune_strength: 0.85, takes: 2, bpm_to: 124 });
    expect(remixBody({ ...RESTYLE, tempo: "keep" }, UPLOAD, PRESETS).bpm_to).toBe(null);
    expect(remixBody({ ...RESTYLE, preset: "acoustic" }, UPLOAD, PRESETS).bpm_to).toBe(null); // preset keeps tempo
    expect(remixBody({ ...RESTYLE, tempo: "custom", bpmCustom: "126" }, UPLOAD, PRESETS).bpm_to).toBe(null); // same as source
    expect(remixBody({ ...RESTYLE, tempo: "custom", bpmCustom: "100" }, UPLOAD, PRESETS).bpm_to).toBe(100);
    expect(remixBody({ ...RESTYLE, preset: "custom", custom: " sufi house ", harmony: true, autotune: false }, UPLOAD, PRESETS))
      .toMatchObject({ preset_key: null, style: "sufi house", harmony: "12", autotune: false });
  });
  it("targetBpm rejects nonsense custom tempos", () => {
    expect(targetBpm({ tempo: "custom", bpmCustom: "9999" }, UPLOAD, PRESETS)).toBe(null);
  });
});

describe("summary + stages", () => {
  it("summarizes the run in words", () => {
    const s = { ...initialState, style: RESTYLE, upload: UPLOAD };
    expect(summary(s, PRESETS)).toBe("Deep House · your voice + ai backing · balanced · 124 BPM · auto-tune · 2 variations");
  });
  it("stageRows marks done/current/todo", () => {
    const job = { progress: { stages: [{ key: "queued" }, { key: "rendering" }, { key: "vocals" }], current: "rendering" } };
    expect(stageRows(job).map((r) => r.state)).toEqual(["done", "current", "todo"]);
  });
});

import { describe, expect, it } from "vitest";
import { canRemix, initialState, reduce, remixBody, stageRows, summary, targetBpm } from "@/features/remix/remixFlow";

const PRESETS = [{ key: "deephouse", label: "Deep House", bpm: 124 }, { key: "acoustic", label: "Acoustic", bpm: 0 }];
const UPLOAD = { id: "u1", bpm: 126, key: "G major", status: "analyzed", stems: [], lyrics: "la" };

describe("remixFlow reducer", () => {
  it("walks start → analyzing → check → style → rendering → result", () => {
    let s = reduce(initialState, { type: "upload_created", upload: { id: "u1", status: "analyzing" }, job: { id: "j1" } });
    expect(s.phase).toBe("analyzing");
    s = reduce(s, { type: "analyzed", upload: UPLOAD }); expect(s.phase).toBe("check");
    s = reduce(s, { type: "to_style" }); expect(canRemix(s)).toBe(true);
    s = reduce(s, { type: "style", patch: { preset: "custom", custom: "" } }); expect(canRemix(s)).toBe(false);
    s = reduce(s, { type: "style", patch: { custom: "sufi house with harmonium" } }); expect(canRemix(s)).toBe(true);
    s = reduce(s, { type: "start_render", job: { id: "j2" }, remixes: [{ id: "r1" }, { id: "r2" }] }); expect(s.phase).toBe("rendering");
    s = reduce(s, { type: "render_done", job: { status: "done" }, upload: UPLOAD, batch: [{ id: "r1", status: "ready" }] });
    expect(s.phase).toBe("result"); expect(s.batch).toHaveLength(1);
    s = reduce(s, { type: "render_failed", job: { status: "failed" }, error: "engine died" });
    expect(s.phase).toBe("style"); expect(s.error).toBe("engine died");
  });
  it("defaults: hybrid, auto-tune on at 85%, two variations", () => {
    expect(initialState.style).toMatchObject({ mode: "hybrid", autotune: true, autotuneStrength: 85, takes: 2, harmony: false });
  });
});

describe("remixBody", () => {
  it("maps the style state to the API contract, omitting a no-op tempo change", () => {
    const body = remixBody(initialState.style, UPLOAD, PRESETS);
    expect(body).toMatchObject({ preset_key: "deephouse", style: null, mode: "hybrid", closeness: 0.5, ai_forward: 1, harmony: "", chops: false, autotune: true, autotune_strength: 0.85, takes: 2, bpm_to: 124 });
    expect(remixBody({ ...initialState.style, tempo: "keep" }, UPLOAD, PRESETS).bpm_to).toBe(null);
    expect(remixBody({ ...initialState.style, preset: "acoustic" }, UPLOAD, PRESETS).bpm_to).toBe(null); // preset keeps tempo
    expect(remixBody({ ...initialState.style, tempo: "custom", bpmCustom: "126" }, UPLOAD, PRESETS).bpm_to).toBe(null); // same as source
    expect(remixBody({ ...initialState.style, tempo: "custom", bpmCustom: "100" }, UPLOAD, PRESETS).bpm_to).toBe(100);
    expect(remixBody({ ...initialState.style, preset: "custom", custom: " sufi house ", harmony: true, autotune: false }, UPLOAD, PRESETS))
      .toMatchObject({ preset_key: null, style: "sufi house", harmony: "12", autotune: false });
  });
  it("targetBpm rejects nonsense custom tempos", () => {
    expect(targetBpm({ tempo: "custom", bpmCustom: "9999" }, UPLOAD, PRESETS)).toBe(null);
  });
});

describe("summary + stages", () => {
  it("summarizes the run in words", () => {
    const s = { ...initialState, upload: UPLOAD };
    expect(summary(s, PRESETS)).toBe("Deep House · your voice + ai backing · balanced · 124 BPM · auto-tune · 2 variations");
  });
  it("stageRows marks done/current/todo", () => {
    const job = { progress: { stages: [{ key: "queued" }, { key: "rendering" }, { key: "vocals" }], current: "rendering" } };
    expect(stageRows(job).map((r) => r.state)).toEqual(["done", "current", "todo"]);
  });
});

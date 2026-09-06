import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { parseFrame } from "@/lib/sse";
import { parseSections, replaceSection, serializeSections, streamedSections } from "@/lib/lyrics";
import { canGenerate, canWrite, initialState, reduce, songBody, stageRows } from "@/features/create/createFlow";
import { readInflight, useJob } from "@/features/create/useJob";

describe("sse parseFrame", () => {
  it("returns the JSON of each data line and tolerates non-JSON", () => {
    expect(parseFrame('event: message\ndata: {"type":"delta","text":"la"}\ndata: plain')).toEqual([{ type: "delta", text: "la" }, { type: "text", text: "plain" }]);
  });
});

describe("lyrics sections", () => {
  const txt = "[Intro]\nOoh\n\n[Verse 1]\nA\nB\n\n[Chorus - anthemic]\nC\n";
  it("parses, replaces and round-trips", () => {
    const s = parseSections(txt);
    expect(s.map((x) => x.tag)).toEqual(["Intro", "Verse 1", "Chorus - anthemic"]);
    expect(parseSections(serializeSections(s))).toEqual(s);
    expect(replaceSection(s, 1, ["Z"])[1].lines).toEqual(["Z"]);
    expect(s[1].lines).toEqual(["A", "B"]); // immutable
  });
  it("reports the open tag while streaming", () => {
    expect(streamedSections("[Verse 1]\nhalf a li").openTag).toBe("Verse 1");
    expect(streamedSections("").openTag).toBe(null);
  });
});

describe("createFlow reducer", () => {
  const brief = { titles: ["A", "B"], style_caption: "pop", bpm: 118, key: "D", vocal_language: "en", duration_s: 150, structure: ["Verse 1"] };
  it("walks compose → briefing → writing → ready → rendering → result", () => {
    let s = reduce(initialState, { type: "compose", patch: { keywords: "late night" } });
    expect(canWrite(s)).toBe(true);
    s = reduce(s, { type: "start_brief" }); expect(s.phase).toBe("briefing"); expect(canWrite(s)).toBe(false);
    s = reduce(s, { type: "brief_ready", brief, engineCaption: "pop, female lead vocal" }); expect(s.phase).toBe("writing");
    s = reduce(s, { type: "lyrics_delta", text: "[Verse 1]\nla" }); expect(s.lyricsText).toContain("la");
    s = reduce(s, { type: "lyrics_done", lyrics: "[Verse 1]\nla\n", sections: [{ tag: "Verse 1", lines: ["la"] }] });
    expect(s.phase).toBe("ready"); expect(canGenerate(s)).toBe(true);
    expect(songBody(s)).toMatchObject({ title: "A", style: "pop, female lead vocal", lyrics: "[Verse 1]\nla\n", bpm: 118, vocal_language: "en" });
    s = reduce(s, { type: "pick_title", index: 1 }); expect(songBody(s).title).toBe("B");
    s = reduce(s, { type: "start_render", song: { id: "s1" }, job: { id: "j1", status: "queued" } }); expect(s.phase).toBe("rendering");
    s = reduce(s, { type: "render_done", job: { status: "done" }, song: { id: "s1" }, takes: [{ id: "g1" }] });
    expect(s.phase).toBe("result"); expect(s.takes).toHaveLength(1);
  });
  it("instrumental sends empty lyrics and a failed render returns to ready with the error", () => {
    let s = reduce(initialState, { type: "compose", patch: { vocal: "instrumental", keywords: "x" } });
    s = reduce(s, { type: "brief_ready", brief, engineCaption: "c" });
    s = reduce(s, { type: "lyrics_done", lyrics: "", sections: [{ tag: "Verse 1", lines: ["la"] }] });
    expect(songBody(s).lyrics).toBe("");
    s = reduce(s, { type: "render_failed", job: { status: "failed" }, error: "engine died" });
    expect(s.phase).toBe("ready"); expect(s.error).toBe("engine died");
  });
  it("maps job progress to stage states", () => {
    const job = { progress: { stages: [{ key: "queued" }, { key: "rendering" }, { key: "mastering" }], current: "rendering" } };
    expect(stageRows(job).map((r) => r.state)).toEqual(["done", "current", "todo"]);
    expect(stageRows({ progress: { ...job.progress, current: "done" } }).map((r) => r.state)).toEqual(["done", "done", "done"]);
  });
});

describe("useJob", () => {
  beforeEach(() => { vi.useFakeTimers(); localStorage.clear(); });
  afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });
  const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(0); });

  it("polls to a terminal state, persists the in-flight id and clears it when done", async () => {
    const statuses = ["queued", "running", "done"];
    let n = 0;
    global.fetch = vi.fn(async () => ({ ok: true, json: async () => ({ id: "j1", status: statuses[Math.min(n++, 2)], progress: null }) }));
    const onDone = vi.fn();
    const { result } = renderHook(() => useJob({ songId: "s1", intervalMs: 100, onDone }));
    await act(async () => { result.current.track("j1"); });
    await flush();
    expect(readInflight("s1")).toBe("j1");
    expect(result.current.job.status).toBe("queued");
    await act(async () => { await vi.advanceTimersByTimeAsync(100); });
    expect(result.current.job.status).toBe("running");
    await act(async () => { await vi.advanceTimersByTimeAsync(100); });
    expect(result.current.job.status).toBe("done");
    expect(onDone).toHaveBeenCalledTimes(1);
    expect(readInflight("s1")).toBe(null);
    expect(global.fetch).toHaveBeenCalledTimes(3);
  });

  it("re-attaches to an in-flight job after a reload", async () => {
    localStorage.setItem("riff:job:s2", "j2");
    global.fetch = vi.fn(async () => ({ ok: true, json: async () => ({ id: "j2", status: "done", progress: null }) }));
    const onDone = vi.fn();
    renderHook(() => useJob({ songId: "s2", intervalMs: 100, onDone }));
    await flush();
    expect(onDone).toHaveBeenCalledTimes(1);
    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining("/jobs/j2"), expect.anything());
    expect(readInflight("s2")).toBe(null);
  });

  it("keeps polling through a transient API error", async () => {
    let n = 0;
    global.fetch = vi.fn(async () => (n++ === 0 ? { ok: false, status: 502, json: async () => ({}) } : { ok: true, json: async () => ({ id: "j3", status: "done" }) }));
    const onDone = vi.fn();
    const { result } = renderHook(() => useJob({ songId: "s3", intervalMs: 100, onDone }));
    await act(async () => { result.current.track("j3"); });
    await flush();
    expect(result.current.error).toContain("502");
    await act(async () => { await vi.advanceTimersByTimeAsync(100); });
    expect(onDone).toHaveBeenCalledTimes(1);
  });
});

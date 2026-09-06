import { describe, expect, it } from "vitest";
import { engineNotice, songRows, summarizeHealth } from "@/lib/health";

describe("summarizeHealth", () => {
  it("reports the API down when there is no payload", () => {
    expect(summarizeHealth(null)[0]).toMatchObject({ key: "api", tone: "down" });
  });
  it("maps db/engine/worker states to tones", () => {
    const rows = summarizeHealth({ version: "0.1.0", env: "development", db: { ok: true },
      engine: { provider: "acestep", ok: true, loaded_model: "acestep-v15-turbo", models_initialized: false },
      worker: { enabled: true, running: true } });
    expect(rows.map((r) => r.tone)).toEqual(["ok", "ok", "ok", "ok"]);
    expect(rows[2].detail).toContain("loads on first song");
  });
  it("shows the engine down with its error and the worker warn while starting", () => {
    const rows = summarizeHealth({ version: "0.1.0", env: "development", db: { ok: false },
      engine: { provider: "acestep", ok: false, error: "connect refused" }, worker: { enabled: true, running: false } });
    expect(rows[1].tone).toBe("down");
    expect(rows[2]).toMatchObject({ tone: "down", detail: "connect refused" });
    expect(rows[3].tone).toBe("warn");
  });
});

describe("songRows", () => {
  it("sorts newest first and counts takes", () => {
    const rows = songRows([
      { id: "a", title: "Old", status: "ready", created_at: "2026-09-01T00:00:00Z", generations: [{}, {}], style: "pop" },
      { id: "b", title: "New", status: "draft", created_at: "2026-09-06T00:00:00Z", generations: [], style: "folk" },
    ]);
    expect(rows.map((r) => r.title)).toEqual(["New", "Old"]);
    expect(rows[1].takes).toBe(2);
  });
});

describe("engineNotice", () => {
  const ok = { db: { ok: true }, engine: { ok: true }, worker: { enabled: true, running: true } };
  it("says nothing before the first check or when everything is up", () => {
    expect(engineNotice(undefined)).toBe(null);
    expect(engineNotice(ok)).toBe(null);
  });
  it("names the one thing that's down, with the command to fix it", () => {
    expect(engineNotice(null)).toMatchObject({ command: "pnpm dev" });
    expect(engineNotice({ ...ok, db: { ok: false } })).toMatchObject({ command: "pnpm docker:up" });
    expect(engineNotice({ ...ok, engine: { ok: false } })).toMatchObject({ title: "The music engine is offline", command: "scripts/engine.sh start" });
    expect(engineNotice({ ...ok, worker: { enabled: true, running: false } })).toMatchObject({ title: "The render worker isn't running" });
  });
  it("prefers the deepest failure — a dead API isn't reported as a dead engine", () => {
    expect(engineNotice({ db: { ok: false }, engine: { ok: false }, worker: { running: false } }).command).toBe("pnpm docker:up");
  });
});

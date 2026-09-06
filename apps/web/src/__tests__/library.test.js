import { describe, expect, it } from "vitest";
import { coverGradient, defaultTake, filterSongs, sortSongs, statusChip, takesByBatch } from "@/lib/library";

const g = (id, batch, idx, fav = false, at = "2026-09-06T10:00:00Z") => ({ id, batch_id: batch, take_index: idx, is_favorite: fav, created_at: at });
const SONGS = [
  { id: "a", title: "Run With Me", style: "pop, synth", lyrics: "neon city", keywords: "drive", status: "ready", created_at: "2026-09-06T14:00:00Z", generations: [g("g1", "b1", 1, true), g("g2", "b1", 2)] },
  { id: "b", title: "Gravel Road", style: "folk, harmonica", lyrics: "porch light", keywords: "", status: "draft", created_at: "2026-09-06T15:00:00Z", generations: [] },
  { id: "c", title: "Needle Talk", style: "boom-bap", lyrics: "crates", keywords: "", status: "rendering", created_at: "2026-09-06T16:00:00Z", generations: [] },
];

describe("filterSongs", () => {
  it("searches title, style, lyrics and keywords, case-insensitively", () => {
    expect(filterSongs(SONGS, { q: "NEON" }).map((s) => s.id)).toEqual(["a"]);
    expect(filterSongs(SONGS, { q: "harmonica" }).map((s) => s.id)).toEqual(["b"]);
    expect(filterSongs(SONGS, { q: "drive" }).map((s) => s.id)).toEqual(["a"]);
    expect(filterSongs(SONGS, { q: "zzz" })).toEqual([]);
  });
  it("filters kept / ready / rendering", () => {
    expect(filterSongs(SONGS, { filter: "kept" }).map((s) => s.id)).toEqual(["a"]);
    expect(filterSongs(SONGS, { filter: "ready" }).map((s) => s.id)).toEqual(["a"]);
    expect(filterSongs(SONGS, { filter: "rendering" }).map((s) => s.id)).toEqual(["c"]);
    expect(filterSongs(SONGS, { filter: "all" })).toHaveLength(3);
  });
});

describe("sortSongs", () => {
  it("newest first by default, by title, by takes", () => {
    expect(sortSongs(SONGS).map((s) => s.id)).toEqual(["c", "b", "a"]);
    expect(sortSongs(SONGS, "title").map((s) => s.id)).toEqual(["b", "c", "a"]);
    expect(sortSongs(SONGS, "takes")[0].id).toBe("a");
    expect(SONGS[0].id).toBe("a"); // input untouched
  });
});

describe("takes", () => {
  it("groups by batch newest first and orders takes", () => {
    const gens = [g("x2", "old", 2, false, "2026-09-01T00:00:00Z"), g("x1", "old", 1, false, "2026-09-01T00:00:00Z"), g("y1", "new", 1, false, "2026-09-05T00:00:00Z")];
    const b = takesByBatch(gens);
    expect(b.map((x) => x.batch_id)).toEqual(["new", "old"]);
    expect(b[1].takes.map((t) => t.id)).toEqual(["x1", "x2"]);
  });
  it("defaultTake prefers a kept take, else the newest batch's first", () => {
    expect(defaultTake(SONGS[0]).id).toBe("g1");
    expect(defaultTake({ generations: [g("q", "b", 2), g("p", "b", 1)] }).id).toBe("p");
    expect(defaultTake(SONGS[1])).toBe(null);
  });
  it("statusChip reflects takes and state", () => {
    expect(statusChip(SONGS[0])).toEqual({ text: "2 takes", tone: "ready" });
    expect(statusChip(SONGS[1]).text).toBe("draft");
    expect(statusChip(SONGS[2]).tone).toBe("rendering");
  });
});

describe("coverGradient", () => {
  it("is deterministic and differs between titles", () => {
    expect(coverGradient("Run With Me")).toBe(coverGradient("Run With Me"));
    expect(coverGradient("Run With Me")).not.toBe(coverGradient("Needle Talk"));
    expect(coverGradient("x")).toMatch(/^linear-gradient\(135deg, hsl\(\d+ 70% 52%\), hsl\(\d+ 65% 30%\)\)$/);
  });
});

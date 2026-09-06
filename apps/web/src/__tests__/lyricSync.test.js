import { describe, expect, it } from "vitest";
import { activeIndex, isApproximate, isSynced, seekTarget, toText } from "@/lib/lyricSync";
import { ITEM_FILTERS, filterItems, libraryItems, sortItems } from "@/lib/libraryItems";

const SEGS = [
  { text: "[Verse 1]", tag: true, start: 0, end: 0 },
  { text: "Bolne se sach badalta nahin", start: 0, end: 3 },
  { text: "a line nobody sang" },                      // never heard → no time
  { text: "Khamosh rehne se koi samajhta nahin", start: 3.5, end: 7 },
];

describe("activeIndex", () => {
  it("lights the line that is sounding, and holds it through the gap to the next one", () => {
    expect(activeIndex(SEGS, 0)).toBe(1);      // the tag and the first line share t=0; the LINE wins (later index)
    expect(activeIndex(SEGS, 2.9)).toBe(1);
    expect(activeIndex(SEGS, 3.2)).toBe(1);    // in the gap — stays on the last line that started
    expect(activeIndex(SEGS, 4)).toBe(3);
    expect(activeIndex(SEGS, 99)).toBe(3);     // past the end, the last line stays lit
  });
  it("is forgiving just before a line starts, so the highlight isn't always late", () => {
    expect(activeIndex(SEGS, 3.4)).toBe(3);
  });
  it("returns -1 with nothing to go on", () => {
    expect(activeIndex([], 5)).toBe(-1);
    expect(activeIndex(SEGS, undefined)).toBe(-1);
    expect(activeIndex([{ text: "x" }], 5)).toBe(-1);
  });
});

describe("segment helpers", () => {
  it("knows when there is enough timing to sync", () => {
    expect(isSynced(SEGS)).toBe(true);
    expect(isSynced([{ text: "x" }])).toBe(false);
    expect(isSynced(null)).toBe(false);
  });
  it("seeks only to timed lines", () => {
    expect(seekTarget(SEGS, 1)).toBe(0);
    expect(seekTarget(SEGS, 2)).toBe(null);
  });
  it("knows when the timing is a spread rather than a match", () => {
    expect(isApproximate(SEGS)).toBe(false);
    expect(isApproximate([{ text: "a", start: 0, approx: true }, { text: "b", start: 4, approx: true }])).toBe(true);
    expect(isApproximate([{ text: "a", start: 0, approx: true }, { text: "b", start: 4 }])).toBe(false);
    expect(isApproximate([{ text: "x" }])).toBe(false);
  });
  it("renders back to text", () => {
    expect(toText(SEGS).split("\n")).toHaveLength(4);
  });
});

const SONGS = [{ id: "s1", title: "Run With Me", style: "pop", lyrics: "neon", keywords: "", status: "ready", created_at: "2026-09-02T00:00:00Z", generations: [{ is_favorite: true }, {}], bpm: 118, key: "D", duration_s: 150, vocal_language: "en" }];
const UPLOADS = [
  { id: "u1", title: "Aqeel Test 1", status: "analyzed", created_at: "2026-09-05T00:00:00Z", bpm: 126.4, key: "G minor", duration_s: 112, vocal_language: "ur", lyrics: "bharosa karo",
    remixes: [{ status: "ready", direction: "Emotional ballad", is_favorite: false, style: "" }, { status: "failed", direction: "x", style: "" }] },
  { id: "u2", title: "Not remixed", status: "analyzed", created_at: "2026-09-06T00:00:00Z", bpm: null, key: null, duration_s: 60, vocal_language: "en", lyrics: "", remixes: [] },
];

describe("libraryItems", () => {
  it("merges songs and remixed uploads into one sortable list", () => {
    const items = libraryItems(SONGS, UPLOADS);
    expect(items.map((i) => i.kind)).toEqual(["song", "remix", "remix"]);
    const u1 = items[1];
    expect(u1).toMatchObject({ title: "Aqeel Test 1", href: "/library/upload/u1", count: 1, status: "ready", bpm: 126 });
    expect(u1.subtitle).toContain("Emotional ballad");
    expect(items[2].subtitle).toBe("Analyzed — not remixed yet");
    expect(items[2].status).toBe("draft");
  });
  it("filters by kind, keeps and text across both kinds", () => {
    const items = libraryItems(SONGS, UPLOADS);
    expect(filterItems(items, { filter: "songs" }).map((i) => i.id)).toEqual(["s1"]);
    expect(filterItems(items, { filter: "remixes" }).map((i) => i.id)).toEqual(["u1", "u2"]);
    expect(filterItems(items, { filter: "kept" }).map((i) => i.id)).toEqual(["s1"]);
    expect(filterItems(items, { q: "bharosa" }).map((i) => i.id)).toEqual(["u1"]);
    expect(filterItems(items, { q: "ballad" }).map((i) => i.id)).toEqual(["u1"]);
    expect(filterItems(items, { q: "neon" }).map((i) => i.id)).toEqual(["s1"]);
    expect(ITEM_FILTERS.map((f) => f[0])).toEqual(["all", "songs", "remixes", "kept"]);
  });
  it("sorts newest first across kinds", () => {
    expect(sortItems(libraryItems(SONGS, UPLOADS)).map((i) => i.id)).toEqual(["u2", "u1", "s1"]);
    expect(sortItems(libraryItems(SONGS, UPLOADS), "title").map((i) => i.title)[0]).toBe("Aqeel Test 1");
  });
});

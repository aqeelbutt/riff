import { describe, expect, it } from "vitest";
import { CALLOUT_W, coachKey, hasSeenCoach, markCoachSeen, placeCallout, spotlightRect, stepAfter, visiblePart } from "@/lib/coach";

const FRAME = { width: 1040, height: 800 };
const SIZE = { width: CALLOUT_W, height: 190 };
const overlaps = (p, a) =>
  !(p.left + SIZE.width <= a.left || p.left >= a.left + a.width ||
    p.top + SIZE.height <= a.top || p.top >= a.top + a.height);
const within = (p) =>
  p.left >= 12 && p.top >= 12 && p.left + SIZE.width <= FRAME.width - 12 && p.top + SIZE.height <= FRAME.height - 12;

describe("placeCallout", () => {
  it("uses the preferred side when it fits", () => {
    const anchor = { top: 120, left: 40, width: 480, height: 220 };
    expect(placeCallout({ anchor, frame: FRAME, size: SIZE, prefer: "right" }).side).toBe("right");
  });

  it("falls back to another side rather than covering the thing it describes", () => {
    // A full-width anchor low in a narrow frame: neither side has room, so it must go above.
    const frame = { width: 700, height: 800 };
    const anchor = { top: 420, left: 20, width: 660, height: 330 };
    const p = placeCallout({ anchor, frame, size: SIZE, prefer: "left" });
    expect(p.side).toBe("above");
    expect(overlaps(p, anchor)).toBe(false);
  });

  it("never covers the spotlight and never leaves the frame, wherever the anchor is", () => {
    for (const top of [0, 200, 470, 700])
      for (const left of [0, 300, 700])
        for (const prefer of ["below", "above", "left", "right"]) {
          const anchor = { top, left, width: 300, height: 120 };
          const p = placeCallout({ anchor, frame: FRAME, size: SIZE, prefer });
          expect(overlaps(p, anchor), `overlap at ${top}/${left}/${prefer}`).toBe(false);
          expect(within(p), `outside at ${top}/${left}/${prefer}`).toBe(true);
        }
  });

  it("docks to the bottom when the target is too big to sit beside", () => {
    // A panel taller than the window: an overlap is unavoidable, so it should be a deliberate dock, not a collision.
    const anchor = { top: 10, left: 10, width: 1020, height: 780 };
    const p = placeCallout({ anchor, frame: FRAME, size: SIZE });
    expect(p.side).toBe("docked");
    expect(within(p)).toBe(true);
    expect(p.top).toBe(FRAME.height - SIZE.height - 12);
  });

  it("keeps its own heading on screen when the callout is taller than the window", () => {
    // A short window (a laptop with the browser half-height): an unclamped dock puts the title off the top.
    const frame = { width: 851, height: 338 };
    const p = placeCallout({ anchor: { top: 0, left: 500, width: 320, height: 700 }, frame, size: { width: CALLOUT_W, height: 330 } });
    expect(p.side).toBe("docked");
    expect(p.top).toBeGreaterThanOrEqual(12);
    expect(p.maxHeight).toBeLessThanOrEqual(frame.height);
  });

  it("places against the visible part of a panel that runs off the screen, not its full height", () => {
    // Scrolled so the section starts above the fold and ends just past mid-screen: there IS room below it.
    const anchor = { top: -600, left: 40, width: 620, height: 1000 };
    const p = placeCallout({ anchor, frame: FRAME, size: SIZE, prefer: "below" });
    expect(p.side).toBe("below");
    expect(p.top).toBeGreaterThanOrEqual(400); // below the visible bottom edge (400), not below -600+1000
  });
});

describe("visiblePart", () => {
  it("trims an anchor to what's actually on screen", () => {
    expect(visiblePart({ top: -50, left: 10, width: 100, height: 300 }, { width: 500, height: 400 }))
      .toEqual({ top: 0, left: 10, width: 100, height: 250 });
    expect(visiblePart({ top: 350, left: 0, width: 100, height: 300 }, { width: 500, height: 400 }))
      .toEqual({ top: 350, left: 0, width: 100, height: 50 });
  });

  it("reports no height for an anchor scrolled fully out of view", () => {
    expect(visiblePart({ top: -400, left: 0, width: 100, height: 100 }, { width: 500, height: 400 }).height).toBe(0);
  });
});

describe("spotlightRect", () => {
  it("pads the anchor on every side", () => {
    expect(spotlightRect({ top: 100, left: 50, width: 200, height: 40 }, 4))
      .toEqual({ top: 96, left: 46, width: 208, height: 48 });
  });
});

describe("seen-flag", () => {
  const store = () => {
    const m = new Map();
    return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => m.set(k, v) };
  };

  it("is unseen until marked", () => {
    const s = store();
    expect(hasSeenCoach("lyric-sync", s)).toBe(false);
    markCoachSeen("lyric-sync", s);
    expect(hasSeenCoach("lyric-sync", s)).toBe(true);
  });

  it("namespaces the key so coaches don't collide", () => {
    const s = store();
    markCoachSeen("lyric-sync", s);
    expect(hasSeenCoach("remix", s)).toBe(false);
    expect(coachKey("lyric-sync")).toBe("riff:coach:lyric-sync");
  });

  it("treats unreadable storage as unseen instead of throwing", () => {
    const boom = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } };
    expect(hasSeenCoach("lyric-sync", boom)).toBe(false);
    expect(markCoachSeen("lyric-sync", boom)).toBe(false);
  });
});

describe("stepAfter", () => {
  it("advances, clamps at zero, and reports done past the end", () => {
    expect(stepAfter(0, 1, 4)).toEqual({ index: 1, done: false });
    expect(stepAfter(0, -1, 4)).toEqual({ index: 0, done: false });
    expect(stepAfter(3, 1, 4)).toEqual({ index: 3, done: true });
  });
});

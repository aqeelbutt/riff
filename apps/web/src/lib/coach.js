/** The walkthrough coach: where a callout sits, and whether someone has already seen it.
 *  Kept pure so the placement maths is testable without a DOM — the component only measures and renders. */

export const CALLOUT_W = 314;

const SIDES = ["below", "above", "right", "left"];

/** Candidate top-left for one side, in frame coordinates. */
function candidate(side, a, frame, size, pad) {
  const maxTop = frame.height - size.height - 12;
  switch (side) {
    case "right": return { left: a.left + a.width + pad, top: Math.min(a.top, maxTop) };
    case "left": return { left: a.left - size.width - pad, top: Math.min(a.top, maxTop) };
    case "above": return { left: a.left + a.width - size.width, top: a.top - size.height - pad };
    default: return { left: a.left + a.width - size.width, top: a.top + a.height + pad };
  }
}

const inside = (p, frame, size, edge) =>
  p.left >= edge && p.top >= edge &&
  p.left + size.width <= frame.width - edge && p.top + size.height <= frame.height - edge;

/** The part of the anchor actually on screen. A section can be taller than the window, and placing against its
 *  full height finds room that isn't really there — every side then "fails" and the callout lands on top of it. */
export function visiblePart(anchor, frame) {
  const top = Math.max(anchor.top, 0);
  const bottom = Math.min(anchor.top + anchor.height, frame.height);
  return { left: anchor.left, width: anchor.width, top, height: Math.max(0, bottom - top) };
}

/**
 * Place the callout beside the thing it describes and never on top of it.
 * Every candidate sits outside the anchor by construction, so "fits inside the frame" is the only test.
 * When the target is too big to sit beside — a panel taller than the window — dock to the bottom edge instead:
 * an overlap is then unavoidable, and a consistent dock reads as deliberate where a random collision doesn't.
 */
export function placeCallout({ anchor, frame, size = { width: CALLOUT_W, height: 190 }, prefer = "below", pad = 14, edge = 12 }) {
  const a = visiblePart(anchor, frame);
  const order = [prefer, ...SIDES.filter((s) => s !== prefer)];
  for (const side of order) {
    const p = candidate(side, a, frame, size, pad);
    if (inside(p, frame, size, edge)) return { ...p, side };
  }
  // Clamped, because on a short window the callout can be taller than the frame and an unclamped dock puts its
  // heading off the top of the screen. `maxHeight` lets the component scroll the body rather than overflow.
  return {
    left: Math.max(edge, Math.min(a.left + a.width / 2 - size.width / 2, frame.width - size.width - edge)),
    top: Math.max(edge, frame.height - size.height - edge),
    maxHeight: Math.max(120, frame.height - edge * 2),
    side: "docked",
  };
}

/** The rectangle the spotlight cuts, padded a little so the ring doesn't crowd the element. */
export const spotlightRect = (anchor, ring = 4) => ({
  top: anchor.top - ring, left: anchor.left - ring,
  width: anchor.width + ring * 2, height: anchor.height + ring * 2,
});

/* ---- seen-flag ------------------------------------------------------------
 * Per-browser, and deliberately not per-song: the walkthrough teaches the feature once, not once per page.
 * Storage can throw (private windows, blocked site data), so every access is guarded and a failure just
 * means the coach behaves as if it hadn't been seen — annoying at worst, never a crash. */

export const coachKey = (name) => `riff:coach:${name}`;

export function hasSeenCoach(name, store) {
  try { return (store ?? globalThis.localStorage)?.getItem(coachKey(name)) === "1"; }
  catch { return false; }
}

export function markCoachSeen(name, store) {
  try { (store ?? globalThis.localStorage)?.setItem(coachKey(name), "1"); return true; }
  catch { return false; }
}

/** Step index after a move, clamped. `done` is true when Next runs off the end. */
export function stepAfter(i, delta, total) {
  const n = i + delta;
  if (n >= total) return { index: total - 1, done: true };
  return { index: Math.max(0, n), done: false };
}

/** Lyrics that follow playback. Segments come from the backend's `align` job: [{text, start?, end?, tag?}].
 *  Lines Whisper never heard carry no time — they render, but never highlight, rather than guessing a position. */

/** Index of the line that should be lit at time `t`, or -1. A line stays lit until the next timed line starts, so the
 *  gaps between segments don't blink the highlight off. */
export function activeIndex(segments, t) {
  if (!segments?.length || typeof t !== "number") return -1;
  let active = -1;
  for (let i = 0; i < segments.length; i++) {
    const s = segments[i];
    if (typeof s.start !== "number") continue;
    if (s.start <= t + 0.15) active = i;
    else break;
  }
  return active;
}

/** True when there is enough timing to be worth showing as a synced view. */
export const isSynced = (segments) => !!segments?.some((s) => typeof s.start === "number");

/** Where to seek when someone clicks a line (null when that line has no time). */
export const seekTarget = (segments, i) => (typeof segments?.[i]?.start === "number" ? segments[i].start : null);

/** Plain text back out of segments — for copying or a static view. */
export const toText = (segments) => (segments || []).map((s) => s.text).join("\n");

/** True when every timed line came from the proportional fallback (different scripts) rather than a text match. */
export const isApproximate = (segments) => {
  const timed = (segments || []).filter((s) => typeof s.start === "number" && !s.tag);
  return timed.length > 0 && timed.every((s) => s.approx);
};

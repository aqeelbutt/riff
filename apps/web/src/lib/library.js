/** Pure helpers for the Library — filter, sort, grouping, cover art. Unit-tested, framework-free. */

export const FILTERS = [["all", "All"], ["kept", "♥ Kept"], ["ready", "Ready"], ["rendering", "Rendering"]];
export const SORTS = [["new", "Newest"], ["title", "Title"], ["takes", "Most takes"]];

export const keptCount = (song) => (song.generations || []).filter((g) => g.is_favorite).length;

export function filterSongs(songs, { q = "", filter = "all" } = {}) {
  const needle = q.trim().toLowerCase();
  return (songs || []).filter((s) => {
    if (filter === "kept" && keptCount(s) === 0) return false;
    if ((filter === "ready" || filter === "rendering") && s.status !== filter) return false;
    if (!needle) return true;
    return [s.title, s.style, s.lyrics, s.keywords].some((t) => (t || "").toLowerCase().includes(needle));
  });
}

export function sortSongs(songs, sort = "new") {
  const arr = [...(songs || [])];
  if (sort === "title") return arr.sort((a, b) => a.title.localeCompare(b.title));
  if (sort === "takes") return arr.sort((a, b) => (b.generations?.length || 0) - (a.generations?.length || 0) || cmpDate(a, b));
  return arr.sort(cmpDate);
}
const cmpDate = (a, b) => new Date(b.created_at) - new Date(a.created_at);

/** Deterministic two-hue gradient from a string (title/id) so every song gets its own cover. */
export function coverGradient(seed = "") {
  let h = 0;
  for (const ch of String(seed)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  const h1 = h % 360, h2 = (h1 + 40 + (h % 60)) % 360;
  return `linear-gradient(135deg, hsl(${h1} 70% 52%), hsl(${h2} 65% 30%))`;
}

/** Group a song's takes by batch (a generate run), newest batch first, take_index within. */
export function takesByBatch(generations) {
  const groups = new Map();
  for (const g of generations || []) {
    if (!groups.has(g.batch_id)) groups.set(g.batch_id, { batch_id: g.batch_id, created_at: g.created_at, takes: [] });
    groups.get(g.batch_id).takes.push(g);
  }
  return [...groups.values()]
    .map((b) => ({ ...b, takes: [...b.takes].sort((x, y) => x.take_index - y.take_index) }))
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
}

/** The take to play when someone presses play on a song: the first kept one, else the newest batch's first. */
export function defaultTake(song) {
  const gens = song?.generations || [];
  return gens.find((g) => g.is_favorite) || takesByBatch(gens)[0]?.takes[0] || null;
}

export const fmtDur = (s) => `${Math.floor((s || 0) / 60)}:${String(Math.floor((s || 0) % 60)).padStart(2, "0")}`;
export const takeLabel = (g) => `Take ${String.fromCharCode(64 + (g.take_index || 1))}`;

export function statusChip(song) {
  const n = song.generations?.length || 0;
  if (song.status === "ready" && n) return { text: `${n} take${n === 1 ? "" : "s"}`, tone: "ready" };
  if (song.status === "rendering") return { text: "rendering", tone: "rendering" };
  if (song.status === "failed") return { text: "failed", tone: "failed" };
  return { text: "draft", tone: "draft" };
}

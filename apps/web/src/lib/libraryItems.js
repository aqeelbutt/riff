/** The Library holds two kinds of thing: songs you made, and songs you brought in and remixed. One list, one sort. */
import { coverGradient, keptCount } from "./library";

const remixesReady = (u) => (u.remixes || []).filter((r) => r.status === "ready");

export function libraryItems(songs, uploads) {
  const a = (songs || []).map((s) => ({
    kind: "song", id: s.id, href: `/library/${s.id}`, title: s.title, subtitle: s.style,
    created_at: s.created_at, count: (s.generations || []).length, kept: keptCount(s),
    status: s.status, bpm: s.bpm, key: s.key, duration_s: s.duration_s, language: s.vocal_language,
    art: coverGradient(s.title + s.id), searchable: [s.title, s.style, s.lyrics, s.keywords],
  }));
  const b = (uploads || []).map((u) => {
    const ready = remixesReady(u);
    const first = ready[0];
    return {
      kind: "remix", id: u.id, href: `/library/upload/${u.id}`, title: u.title,
      subtitle: first ? `${first.direction || first.preset_key || "Remix"} · from your upload` : u.status === "analyzed" ? "Analyzed — not remixed yet" : u.status,
      created_at: u.created_at, count: ready.length, kept: ready.filter((r) => r.is_favorite).length,
      status: ready.length ? "ready" : u.status === "failed" ? "failed" : u.status === "analyzed" ? "draft" : "rendering",
      bpm: u.bpm ? Math.round(u.bpm) : null, key: u.key, duration_s: u.duration_s, language: u.vocal_language,
      art: coverGradient(u.title + u.id),
      searchable: [u.title, u.lyrics, ...ready.map((r) => `${r.direction || ""} ${r.style || ""}`)],
    };
  });
  return [...a, ...b];
}

export function filterItems(items, { q = "", filter = "all" } = {}) {
  const needle = q.trim().toLowerCase();
  return (items || []).filter((it) => {
    if (filter === "songs" && it.kind !== "song") return false;
    if (filter === "remixes" && it.kind !== "remix") return false;
    if (filter === "kept" && it.kept === 0) return false;
    if (!needle) return true;
    return (it.searchable || []).some((t) => (t || "").toLowerCase().includes(needle));
  });
}

export function sortItems(items, sort = "new") {
  const arr = [...(items || [])];
  if (sort === "title") return arr.sort((x, y) => x.title.localeCompare(y.title));
  if (sort === "takes") return arr.sort((x, y) => y.count - x.count || byDate(x, y));
  return arr.sort(byDate);
}
const byDate = (x, y) => new Date(y.created_at) - new Date(x.created_at);

export const ITEM_FILTERS = [["all", "All"], ["songs", "Songs"], ["remixes", "Remixes"], ["kept", "♥ Kept"]];

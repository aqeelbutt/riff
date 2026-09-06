"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { API_URL, api } from "@/lib/api";
import { SORTS, coverGradient, defaultTake, fmtDur, takeLabel } from "@/lib/library";
import { ITEM_FILTERS, filterItems, libraryItems, sortItems } from "@/lib/libraryItems";
import { usePlayerCtx } from "@/features/player/PlayerProvider";

const TONE = { ready: "text-mint", rendering: "text-amber", analyzing: "text-amber", failed: "text-acc", draft: "text-ink-2", uploaded: "text-ink-2" };
const trackOf = (song, g) => ({ id: g.id, url: `${API_URL}${g.mp3_url || g.audio_url}`, title: song.title, sub: `${takeLabel(g)} · seed ${g.seed}`, art: coverGradient(song.title + song.id) });

export default function LibraryPage() {
  const [songs, setSongs] = useState(null);
  const [uploads, setUploads] = useState([]);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("new");
  const player = usePlayerCtx();

  useEffect(() => {
    let alive = true;
    const load = () => Promise.all([api("/songs").catch(() => []), api("/uploads").catch(() => [])])
      .then(([s, u]) => { if (alive) { setSongs(s); setUploads(u); } });
    load();
    const t = setInterval(load, 8000); // rendering songs flip to ready without a refresh
    return () => { alive = false; clearInterval(t); };
  }, []);

  const rows = useMemo(() => sortItems(filterItems(libraryItems(songs, uploads), { q, filter }), sort), [songs, uploads, q, filter, sort]);

  return (
    <main className="mx-auto max-w-[1100px] px-6 pb-28 pt-7">
      <h1 className="font-disp text-[30px] font-extrabold leading-none tracking-tight">Library</h1>
      <p className="mt-1.5 text-ink-2">Everything you&apos;ve made and everything you&apos;ve remixed, on this Mac. Play from here; keep the ones you love.</p>

      <div className="my-5 flex flex-wrap items-center gap-2.5">
        <label className="flex min-w-[220px] flex-1 items-center gap-2 rounded-r border border-line bg-sur px-3 py-2">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--ink-3)" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></svg>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search songs and remixes…" aria-label="Search songs" className="flex-1 bg-transparent text-ink outline-none placeholder:text-ink-3" />
        </label>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter">
          {ITEM_FILTERS.map(([k, l]) => <button key={k} type="button" aria-pressed={filter === k} onClick={() => setFilter(k)} className={`rounded-full border px-3 py-1.5 text-[13px] ${filter === k ? "border-acc bg-[var(--acc-soft)] text-ink" : "border-line bg-sur text-ink-2"}`}>{l}</button>)}
        </div>
        <div className="flex gap-0.5 rounded-r-sm border border-line bg-sur p-[3px]" role="group" aria-label="Sort">
          {SORTS.map(([k, l]) => <button key={k} type="button" aria-pressed={sort === k} onClick={() => setSort(k)} className={`rounded-[5px] px-2.5 py-1 text-[12.5px] ${sort === k ? "bg-sur-3 text-ink" : "text-ink-2"}`}>{l}</button>)}
        </div>
      </div>

      {songs === null ? <p className="text-ink-3">Loading…</p> : rows.length === 0 ? (
        <div className="mx-auto mt-[10vh] max-w-[460px] text-center text-ink-2">
          {songs.length === 0 && uploads.length === 0 ? <>Nothing here yet. <Link href="/" className="text-acc">Make your first song →</Link> or <Link href="/remix" className="text-acc">remix one you own →</Link></> : "Nothing matches. Try another word, or clear the filter."}
        </div>
      ) : (
        <div className="grid gap-3.5" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))" }}>
          {rows.map((it) => {
            const song = it.kind === "song" ? songs.find((x) => x.id === it.id) : null;
            const dt = song ? defaultTake(song) : null;
            const remix = it.kind === "remix" ? (uploads.find((u) => u.id === it.id)?.remixes || []).find((r) => r.status === "ready" && (r.is_favorite || true)) : null;
            const track = dt ? trackOf(song, dt) : remix ? { id: remix.id, url: `${API_URL}${remix.mp3_url || remix.audio_url}`, title: it.title, sub: remix.direction || "Remix", art: it.art } : null;
            const playing = track && player.isCurrent(track.id) && player.now.playing;
            const all = song ? song.generations.map((g) => trackOf(song, g)) : track ? [track] : [];
            return (
              <Link key={`${it.kind}:${it.id}`} href={it.href} className={`group relative flex flex-col gap-2.5 rounded-[14px] border bg-sur p-3.5 transition hover:-translate-y-px hover:border-line-2 ${playing ? "border-acc" : "border-line"}`}>
                <div className="relative flex h-[120px] items-end overflow-hidden rounded-[10px] p-2.5" style={{ background: it.art }}>
                  <span className={`absolute left-2.5 top-2.5 rounded-[5px] bg-[rgba(14,16,20,.7)] px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[.08em] ${TONE[it.status] || "text-ink-2"}`}>
                    {it.status === "ready" ? `${it.count} ${it.kind === "song" ? (it.count === 1 ? "take" : "takes") : (it.count === 1 ? "version" : "versions")}` : it.status}
                  </span>
                  {it.kind === "remix" && <span className="absolute right-2.5 top-2.5 rounded-[5px] bg-[rgba(14,16,20,.7)] px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[.08em] text-vio">remix</span>}
                  {it.kept > 0 && <span className="absolute bottom-2.5 right-2.5 text-[15px] text-acc" aria-label="has kept takes">♥</span>}
                  {track && <button type="button" aria-label={`Play ${it.title}`} onClick={(e) => { e.preventDefault(); player.toggle(track, all); }}
                    className={`grid h-9 w-9 place-items-center rounded-full bg-ink text-bg shadow-[0_6px_18px_-6px_rgba(0,0,0,.6)] transition ${playing ? "opacity-100" : "opacity-0 group-hover:opacity-100 focus:opacity-100"}`}>
                    {playing ? <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h4v14H6zM14 5h4v14h-4z" /></svg> : <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M7 5v14l11-7z" /></svg>}</button>}
                </div>
                <b className="font-disp text-[17px] font-bold leading-tight">{it.title}</b>
                <span className="line-clamp-2 text-[12.5px] text-ink-2">{it.subtitle}</span>
                <span className="mt-auto flex gap-2 font-mono text-[11px] text-ink-3">{it.bpm && <span>{it.bpm} BPM</span>}{it.key && <span>{it.key}</span>}<span>{fmtDur(it.duration_s)}</span><span className="ml-auto uppercase">{it.language}</span></span>
              </Link>);
          })}
        </div>
      )}
    </main>
  );
}

"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { API_URL, api } from "@/lib/api";
import { FILTERS, SORTS, coverGradient, defaultTake, filterSongs, fmtDur, keptCount, sortSongs, statusChip, takeLabel } from "@/lib/library";
import { usePlayerCtx } from "@/features/player/PlayerProvider";

const TONE = { ready: "text-mint", rendering: "text-amber", failed: "text-acc", draft: "text-ink-2" };
const trackOf = (song, g) => ({ id: g.id, url: `${API_URL}${g.mp3_url || g.audio_url}`, title: song.title, sub: `${takeLabel(g)} · seed ${g.seed}`, art: coverGradient(song.title + song.id) });

export default function LibraryPage() {
  const [songs, setSongs] = useState(null);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("new");
  const player = usePlayerCtx();

  useEffect(() => {
    let alive = true;
    const load = () => api("/songs").then((s) => alive && setSongs(s)).catch(() => alive && setSongs([]));
    load();
    const t = setInterval(load, 8000); // rendering songs flip to ready without a refresh
    return () => { alive = false; clearInterval(t); };
  }, []);

  const rows = useMemo(() => sortSongs(filterSongs(songs, { q, filter }), sort), [songs, q, filter, sort]);

  return (
    <main className="mx-auto max-w-[1100px] px-6 pb-28 pt-7">
      <h1 className="font-disp text-[30px] font-extrabold leading-none tracking-tight">Library</h1>
      <p className="mt-1.5 text-ink-2">Everything you&apos;ve made, on this Mac. Play from here; keep the takes you love.</p>

      <div className="my-5 flex flex-wrap items-center gap-2.5">
        <label className="flex min-w-[220px] flex-1 items-center gap-2 rounded-r border border-line bg-sur px-3 py-2">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--ink-3)" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></svg>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search titles, styles, lyrics…" aria-label="Search songs" className="flex-1 bg-transparent text-ink outline-none placeholder:text-ink-3" />
        </label>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter">
          {FILTERS.map(([k, l]) => <button key={k} type="button" aria-pressed={filter === k} onClick={() => setFilter(k)} className={`rounded-full border px-3 py-1.5 text-[13px] ${filter === k ? "border-acc bg-[var(--acc-soft)] text-ink" : "border-line bg-sur text-ink-2"}`}>{l}</button>)}
        </div>
        <div className="flex gap-0.5 rounded-r-sm border border-line bg-sur p-[3px]" role="group" aria-label="Sort">
          {SORTS.map(([k, l]) => <button key={k} type="button" aria-pressed={sort === k} onClick={() => setSort(k)} className={`rounded-[5px] px-2.5 py-1 text-[12.5px] ${sort === k ? "bg-sur-3 text-ink" : "text-ink-2"}`}>{l}</button>)}
        </div>
      </div>

      {songs === null ? <p className="text-ink-3">Loading…</p> : rows.length === 0 ? (
        <div className="mx-auto mt-[10vh] max-w-[460px] text-center text-ink-2">
          {songs.length === 0 ? <>Nothing here yet. <Link href="/" className="text-acc">Make your first song →</Link></> : "Nothing matches. Try another word, or clear the filter."}
        </div>
      ) : (
        <div className="grid gap-3.5" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))" }}>
          {rows.map((s) => {
            const chip = statusChip(s), dt = defaultTake(s), playing = dt && player.isCurrent(dt.id) && player.now.playing;
            return (
              <Link key={s.id} href={`/library/${s.id}`} className={`group relative flex flex-col gap-2.5 rounded-[14px] border bg-sur p-3.5 transition hover:-translate-y-px hover:border-line-2 ${playing ? "border-acc" : "border-line"}`}>
                <div className="relative flex h-[120px] items-end overflow-hidden rounded-[10px] p-2.5" style={{ background: coverGradient(s.title + s.id) }}>
                  <span className={`absolute left-2.5 top-2.5 rounded-[5px] bg-[rgba(14,16,20,.7)] px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[.08em] ${TONE[chip.tone]}`}>{chip.text}</span>
                  {keptCount(s) > 0 && <span className="absolute right-2.5 top-2 text-[15px] text-acc" aria-label="has kept takes">♥</span>}
                  {dt && <button type="button" aria-label={`Play ${s.title}`} onClick={(e) => { e.preventDefault(); player.toggle(trackOf(s, dt), s.generations.map((g) => trackOf(s, g))); }}
                    className={`grid h-9 w-9 place-items-center rounded-full bg-ink text-bg shadow-[0_6px_18px_-6px_rgba(0,0,0,.6)] transition ${playing ? "opacity-100" : "opacity-0 group-hover:opacity-100 focus:opacity-100"}`}>
                    {playing ? <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h4v14H6zM14 5h4v14h-4z" /></svg> : <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M7 5v14l11-7z" /></svg>}</button>}
                </div>
                <b className="font-disp text-[17px] font-bold leading-tight">{s.title}</b>
                <span className="line-clamp-2 text-[12.5px] text-ink-2">{s.style}</span>
                <span className="mt-auto flex gap-2 font-mono text-[11px] text-ink-3">{s.bpm && <span>{s.bpm} BPM</span>}{s.key && <span>{s.key}</span>}<span>{fmtDur(s.duration_s)}</span><span className="ml-auto uppercase">{s.vocal_language}</span></span>
              </Link>);
          })}
        </div>
      )}
    </main>
  );
}

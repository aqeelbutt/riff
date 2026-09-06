"use client";
/** App-wide player: ONE <audio>, a current track + optional playlist (A/B, next), and the bottom bar. Mounted in the root layout
 *  so playback survives navigation between Create, Library and a song page. */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { fmt } from "./usePlayer";

const Ctx = createContext(null);

export function PlayerProvider({ children }) {
  const audio = useRef(null);
  const [now, setNow] = useState({ track: null, list: [], playing: false, t: 0, d: 0 });

  useEffect(() => {
    const a = new Audio(); audio.current = a;
    const upd = () => setNow((s) => ({ ...s, t: a.currentTime, d: a.duration || 0, playing: !a.paused && !a.ended }));
    for (const ev of ["timeupdate", "play", "pause", "ended", "loadedmetadata"]) a.addEventListener(ev, upd);
    return () => { a.pause(); a.src = ""; };
  }, []);

  /** track: {id, url, title, sub, art}; list: tracks that A/B and Next cycle through (defaults to [track]). */
  const play = useCallback((track, list) => {
    const a = audio.current; if (!a || !track) return;
    if (a.src !== track.url) { a.src = track.url; a.load(); }
    setNow((s) => ({ ...s, track, list: list && list.length ? list : [track] }));
    a.play().catch(() => {});
  }, []);
  const toggle = useCallback((track, list) => {
    const a = audio.current; if (!a) return;
    if (track && now.track?.id !== track.id) return play(track, list);
    if (!now.track) return;
    if (a.paused) a.play().catch(() => {}); else a.pause();
  }, [now.track, play]);
  const seek = useCallback((frac) => { const a = audio.current; if (a && a.duration) a.currentTime = frac * a.duration; }, []);
  const stop = useCallback(() => { const a = audio.current; if (a) { a.pause(); a.src = ""; } setNow({ track: null, list: [], playing: false, t: 0, d: 0 }); }, []);
  /** Switch to another track in the list at the same position (A/B). */
  const switchTo = useCallback((offset = 1) => {
    const { track, list } = now; if (!track || list.length < 2) return;
    const i = list.findIndex((x) => x.id === track.id);
    const next = list[(i + offset + list.length) % list.length];
    const a = audio.current; const t = a?.currentTime || 0;
    play(next, list);
    if (a) a.currentTime = t;
  }, [now, play]);
  const isCurrent = useCallback((id) => now.track?.id === id, [now.track]);
  const progress = now.d ? now.t / now.d : 0;

  const value = useMemo(() => ({ now, play, toggle, seek, stop, switchTo, isCurrent, progress }), [now, play, toggle, seek, stop, switchTo, isCurrent, progress]);
  return <Ctx.Provider value={value}>{children}<PlayerBar /></Ctx.Provider>;
}

export function usePlayerCtx() {
  const v = useContext(Ctx);
  if (!v) throw new Error("usePlayerCtx outside PlayerProvider");
  return v;
}

const PlayIcon = ({ playing }) => playing ? <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h4v14H6zM14 5h4v14h-4z" /></svg> : <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M7 5v14l11-7z" /></svg>;

function PlayerBar() {
  const p = useContext(Ctx);
  const { track, list, playing, t, d } = p.now;
  if (!track) return null;
  return (
    <div className="fixed inset-x-0 bottom-0 z-30 grid h-[76px] grid-cols-[auto_1fr] items-center gap-4 border-t border-line bg-[color-mix(in_srgb,var(--sur)_92%,transparent)] px-5 backdrop-blur-md md:grid-cols-[auto_1fr_auto]" aria-label="Now playing">
      <div className="flex min-w-0 items-center gap-3"><div className="h-11 w-11 flex-none rounded-lg" style={{ background: track.art || "linear-gradient(135deg,var(--acc),#7a2a12)" }} /><div className="min-w-0"><div className="truncate font-semibold">{track.title}</div><div className="truncate text-xs text-ink-2">{track.sub}</div></div></div>
      <div className="flex items-center gap-3">
        <button type="button" aria-label="Play or pause" onClick={() => p.toggle()} className="grid h-10 w-10 place-items-center rounded-full bg-ink text-bg"><PlayIcon playing={playing} /></button>
        <span className="font-mono text-[11.5px] text-ink-2">{fmt(t)}</span>
        <div className="relative h-1 flex-1 cursor-pointer rounded-full bg-sur-3" onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); p.seek((e.clientX - r.left) / r.width); }}><i className="absolute inset-y-0 left-0 rounded-full bg-acc" style={{ width: `${d ? (t / d) * 100 : 0}%` }} /></div>
        <span className="font-mono text-[11.5px] text-ink-2">{fmt(d)}</span>
      </div>
      <div className="hidden gap-1 md:flex">{list.length > 1 && <button type="button" onClick={() => p.switchTo(1)} className="px-2 py-1.5 text-ink-2 hover:text-ink">A / B</button>}<button type="button" aria-label="Close player" onClick={p.stop} className="px-2 py-1.5 text-ink-3 hover:text-ink">✕</button></div>
    </div>
  );
}

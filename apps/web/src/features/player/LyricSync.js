"use client";
/** Lyrics that follow the audio. Lit line = what's sounding now; click any timed line to jump there.
 *  Lines the aligner never heard still render (dimmed) — they just never light, which is honest about what we know. */
import { useEffect, useRef } from "react";
import { activeIndex, isApproximate, isSynced, seekTarget } from "@/lib/lyricSync";

export function LyricSync({ segments, time, live, onSeek, maxHeight = 520 }) {
  const box = useRef(null);
  const active = live ? activeIndex(segments, time) : -1;
  const synced = isSynced(segments);

  useEffect(() => {
    if (active < 0 || !box.current) return;
    const el = box.current.querySelector(`[data-line="${active}"]`);
    if (!el) return;
    const b = box.current.getBoundingClientRect(), r = el.getBoundingClientRect();
    if (r.top < b.top + 24 || r.bottom > b.bottom - 24) {
      box.current.scrollTo({ top: el.offsetTop - box.current.clientHeight / 2 + el.clientHeight / 2, behavior: "smooth" });
    }
  }, [active]);

  if (!segments?.length) return null;
  return (
    <>
    {isApproximate(segments) && <p data-coach="lyric-approx" className="mb-2 text-[11.5px] text-ink-3">Timing is approximate — the words are yours, the positions are spread across what was heard.</p>}
    <div ref={box} className="overflow-auto text-sm leading-relaxed" style={{ maxHeight }} aria-live={live ? "polite" : "off"}>
      {segments.map((s, i) => {
        const timed = typeof s.start === "number";
        if (s.tag) return <div key={i} data-line={i} className={`mt-3 font-mono text-[11px] first:mt-0 ${active === i ? "text-vio" : "text-vio/60"}`}>{s.text}</div>;
        return (
          <div key={i} data-line={i}
            role={timed ? "button" : undefined} tabIndex={timed ? 0 : undefined}
            onClick={timed ? () => onSeek?.(seekTarget(segments, i)) : undefined}
            onKeyDown={timed ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSeek?.(seekTarget(segments, i)); } } : undefined}
            className={`-mx-1 rounded px-1 py-[3px] transition-colors ${timed ? "cursor-pointer" : ""} ${
              active === i ? "bg-[var(--acc-soft)] font-semibold text-ink" : synced && timed ? "text-ink-2 hover:text-ink" : "text-ink-3"}`}>
            {s.text}
          </div>);
      })}
    </div>
    </>
  );
}

"use client";
import { useEffect, useRef, useState } from "react";
import { loadPeaks } from "./usePlayer";

/** Decoded waveform with a playhead. `progress` in [0,1]. */
export function Wave({ url, progress = 0, accent = false, onSeek, height = 72, label }) {
  const canvas = useRef(null);
  const [peaks, setPeaks] = useState(null);
  useEffect(() => { let alive = true; loadPeaks(url).then((p) => alive && setPeaks(p)); return () => { alive = false; }; }, [url]);
  useEffect(() => {
    const c = canvas.current; if (!c || !peaks) return;
    const dpr = window.devicePixelRatio || 1, W = c.clientWidth * dpr, H = c.clientHeight * dpr;
    c.width = W; c.height = H;
    const ctx = c.getContext("2d"); ctx.clearRect(0, 0, W, H);
    const bw = W / peaks.length;
    peaks.forEach((p, i) => { const h = Math.max(2 * dpr, p * H * 0.86); ctx.fillStyle = accent ? "rgba(255,138,102,.75)" : "rgba(238,240,244,.55)"; ctx.fillRect(i * bw + bw * 0.2, (H - h) / 2, bw * 0.6, h); });
  }, [peaks, accent]);
  return (
    <div className="relative cursor-pointer overflow-hidden rounded-r-sm bg-bg-2" style={{ height }} role="slider" aria-label={label} tabIndex={0}
      aria-valuenow={Math.round(progress * 100)} onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); onSeek?.((e.clientX - r.left) / r.width); }}>
      <canvas ref={canvas} className="block h-full w-full" />
      <div className="pointer-events-none absolute inset-y-0 left-0 border-r-[1.5px] border-acc bg-[var(--acc-soft)]" style={{ width: `${progress * 100}%` }} />
    </div>
  );
}

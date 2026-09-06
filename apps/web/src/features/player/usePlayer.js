"use client";
/** One shared <audio> for the app: play(url, meta), toggle, seek, and decoded peaks for waveforms (cached per url). */
import { useCallback, useEffect, useRef, useState } from "react";

const peaksCache = new Map();

export async function loadPeaks(url, n = 160) {
  if (peaksCache.has(url)) return peaksCache.get(url);
  try {
    const buf = await (await fetch(url)).arrayBuffer();
    const ac = new (window.AudioContext || window.webkitAudioContext)();
    const ab = await ac.decodeAudioData(buf);
    const d = ab.getChannelData(0), blk = Math.floor(d.length / n);
    const p = [];
    for (let i = 0; i < n; i++) { let m = 0; for (let j = 0; j < blk; j += 8) { const v = Math.abs(d[i * blk + j]); if (v > m) m = v; } p.push(m); }
    const mx = Math.max(...p) || 1;
    const out = p.map((x) => x / mx);
    ac.close();
    peaksCache.set(url, out);
    return out;
  } catch { return Array.from({ length: n }, (_, i) => 0.35 + 0.6 * Math.abs(Math.sin(i * 0.37) * Math.cos(i * 0.11))); }
}

export function usePlayer() {
  const audio = useRef(null);
  const [now, setNow] = useState({ url: null, title: "", sub: "", playing: false, t: 0, d: 0 });

  useEffect(() => {
    const a = new Audio(); audio.current = a;
    const upd = () => setNow((s) => ({ ...s, t: a.currentTime, d: a.duration || 0, playing: !a.paused }));
    a.addEventListener("timeupdate", upd); a.addEventListener("play", upd); a.addEventListener("pause", upd); a.addEventListener("ended", upd);
    return () => { a.pause(); a.src = ""; };
  }, []);

  const play = useCallback((url, meta = {}) => {
    const a = audio.current; if (!a) return;
    if (a.src !== url) { a.src = url; a.load(); }
    setNow((s) => ({ ...s, url, ...meta }));
    a.play().catch(() => {});
  }, []);
  const toggle = useCallback((url, meta) => {
    const a = audio.current; if (!a) return;
    if (now.url === url && !a.paused) a.pause(); else play(url, meta);
  }, [now.url, play]);
  const seek = useCallback((frac) => { const a = audio.current; if (a && a.duration) a.currentTime = frac * a.duration; }, []);
  const switchTo = useCallback((url, meta) => { const a = audio.current; const t = a?.currentTime || 0; play(url, meta); if (a) a.currentTime = t; }, [play]);
  const stop = useCallback(() => { const a = audio.current; if (a) { a.pause(); a.currentTime = 0; } setNow({ url: null, title: "", sub: "", playing: false, t: 0, d: 0 }); }, []);

  return { now, play, toggle, seek, switchTo, stop };
}

export const fmt = (s) => `${Math.floor((s || 0) / 60)}:${String(Math.floor((s || 0) % 60)).padStart(2, "0")}`;

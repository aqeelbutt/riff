"use client";
/** Poll a job to a terminal state. Persists the in-flight job id per song (a reload re-attaches instead of paying twice);
 *  pauses polling while the tab is hidden. Mirrors PursuitAI's useAiJob. */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

export const TERMINAL = new Set(["done", "failed", "cancelled"]);
const KEY = (songId) => `riff:job:${songId}`;

export function readInflight(songId) {
  try { return localStorage.getItem(KEY(songId)); } catch { return null; }
}
function writeInflight(songId, jobId) {
  try { jobId ? localStorage.setItem(KEY(songId), jobId) : localStorage.removeItem(KEY(songId)); } catch { /* private mode */ }
}

export function useJob({ songId, intervalMs = 2500, onDone } = {}) {
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const timer = useRef(null);
  const jobIdRef = useRef(null);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  const stop = useCallback(() => { if (timer.current) { clearTimeout(timer.current); timer.current = null; } }, []);

  const tick = useCallback(async () => {
    const id = jobIdRef.current;
    if (!id) return;
    try {
      const j = await api(`/jobs/${id}`);
      setJob(j);
      setError(null);
      if (TERMINAL.has(j.status)) {
        writeInflight(songId, null);
        jobIdRef.current = null;
        onDoneRef.current?.(j);
        return;
      }
    } catch (e) {
      setError(e.message); // keep polling: a transient API blip must not orphan the job
    }
    if (typeof document !== "undefined" && document.hidden) { timer.current = setTimeout(tick, intervalMs * 4); return; }
    timer.current = setTimeout(tick, intervalMs);
  }, [intervalMs, songId]);

  const track = useCallback((jobId) => {
    stop();
    jobIdRef.current = jobId;
    writeInflight(songId, jobId);
    setJob({ id: jobId, status: "queued", progress: null });
    tick();
  }, [songId, stop, tick]);

  // re-attach after a reload
  useEffect(() => {
    if (!songId) return;
    const inflight = readInflight(songId);
    if (inflight) { jobIdRef.current = inflight; tick(); }
    return stop;
  }, [songId, stop, tick]);

  // resume promptly when the tab becomes visible again
  useEffect(() => {
    const onVis = () => { if (!document.hidden && jobIdRef.current) { stop(); tick(); } };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, [stop, tick]);

  return { job, error, track, stop, isActive: !!jobIdRef.current };
}

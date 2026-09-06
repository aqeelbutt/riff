"use client";
/** Ask for line timings for one rendered audio, then poll until they land. `kind` is "generations" | "remixes". */
import { useCallback, useState } from "react";
import { api } from "@/lib/api";

export function useAlign({ kind, onDone }) {
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState(null);

  const align = useCallback(async (id) => {
    setBusyId(id); setError(null);
    try {
      const job = await api(`/${kind}/${id}/align`, { method: "POST" });
      for (let i = 0; i < 60; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        const j = await api(`/jobs/${job.id}`);
        if (j.status === "done") { await onDone?.(); return true; }
        if (j.status === "failed" || j.status === "cancelled") throw new Error(j.error?.split("\n")[0] || `align ${j.status}`);
      }
      throw new Error("aligning took too long");
    } catch (e) { setError(e.message); return false; }
    finally { setBusyId(null); }
  }, [kind, onDone]);

  return { align, busyId, error };
}

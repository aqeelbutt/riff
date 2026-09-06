"use client";
import { useEffect, useState } from "react";
import { api, API_URL } from "@/lib/api";
import { songRows, summarizeHealth } from "@/lib/health";

const TONE = { ok: "bg-mint", warn: "bg-amber", down: "bg-acc" };

export default function Home() {
  const [health, setHealth] = useState(null);
  const [songs, setSongs] = useState([]);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const [h, s] = await Promise.all([api("/health"), api("/songs")]);
        if (alive) { setHealth(h); setSongs(s); setErr(null); }
      } catch (e) { if (alive) setErr(e.message); }
    };
    load();
    const t = setInterval(load, 5000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  const rows = summarizeHealth(err ? null : health);
  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <header className="mb-8 flex items-center gap-3">
        <span className="inline-block h-3 w-3 rotate-45 rounded-[3px] bg-acc shadow-[0_0_0_3px_var(--acc-soft)]" />
        <h1 className="font-disp text-3xl font-extrabold tracking-tight">Riff</h1>
        <span className="ml-auto font-mono text-xs text-ink-3">{API_URL}</span>
      </header>

      <section aria-labelledby="status" className="rounded-r border border-line bg-sur p-4">
        <h2 id="status" className="mb-3 font-mono text-[11px] uppercase tracking-[.1em] text-ink-3">Status</h2>
        <ul className="grid gap-2">
          {rows.map((r) => (
            <li key={r.key} className="flex items-center gap-3 rounded-r-sm bg-bg-2 px-3 py-2">
              <span className={`h-2 w-2 rounded-full ${TONE[r.tone]}`} aria-hidden="true" />
              <span className="font-medium">{r.label}</span>
              <span className="ml-auto font-mono text-xs text-ink-2">{r.detail}</span>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="songs" className="mt-6">
        <h2 id="songs" className="mb-3 font-mono text-[11px] uppercase tracking-[.1em] text-ink-3">Songs</h2>
        {songRows(songs).length === 0 ? (
          <p className="text-ink-2">
            No songs yet. The Create screen lands in Phase 2 — until then: <code className="font-mono text-xs">riff create --lyrics … --style …</code>
          </p>
        ) : (
          <ul className="grid gap-2">
            {songRows(songs).map((s) => (
              <li key={s.id} className="flex items-center gap-3 rounded-r border border-line bg-sur px-4 py-3">
                <span className="font-disp text-lg font-bold">{s.title}</span>
                <span className="truncate text-sm text-ink-2">{s.style}</span>
                <span className="ml-auto font-mono text-xs text-ink-3">{s.takes} take{s.takes === 1 ? "" : "s"} · {s.status}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

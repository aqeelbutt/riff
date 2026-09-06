"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { API_URL, api } from "@/lib/api";
import { coverGradient, fmtDur, keptCount, takeLabel, takesByBatch } from "@/lib/library";
import { parseSections } from "@/lib/lyrics";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { usePlayerCtx } from "@/features/player/PlayerProvider";
import { Wave } from "@/features/player/Wave";
import { useJob } from "@/features/create/useJob";
import { stageRows } from "@/features/create/createFlow";

const trackOf = (song, g) => ({ id: g.id, url: `${API_URL}${g.mp3_url || g.audio_url}`, title: song.title, sub: `${takeLabel(g)} · seed ${g.seed}`, art: coverGradient(song.title + song.id) });
const PlayIcon = ({ playing }) => playing ? <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h4v14H6zM14 5h4v14h-4z" /></svg> : <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M7 5v14l11-7z" /></svg>;

export default function SongPage({ id }) {
  const router = useRouter();
  const player = usePlayerCtx();
  const [song, setSong] = useState(null);
  const [missing, setMissing] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [toast, setToast] = useState(null);
  useEffect(() => { if (!toast) return; const t = setTimeout(() => setToast(null), 2200); return () => clearTimeout(t); }, [toast]);

  const load = useCallback(() => api(`/songs/${id}`).then(setSong).catch(() => setMissing(true)), [id]);
  useEffect(() => { load(); }, [load]);

  const { job, track } = useJob({ songId: id, onDone: (j) => { load(); setToast(j.status === "done" ? "New takes are in" : `Render ${j.status}`); } });
  const rendering = job && !["done", "failed", "cancelled"].includes(job.status);
  useEffect(() => { if (!song || song.status !== "rendering" || rendering) return; const t = setInterval(load, 5000); return () => clearInterval(t); }, [song, rendering, load]);

  const moreTakes = async () => {
    try { const j = await api(`/songs/${id}/generate`, { method: "POST", body: { takes: 2 } }); track(j.id); setSong((s) => ({ ...s, status: "rendering" })); }
    catch (e) { setToast(e.message); }
  };
  const keep = async (g) => {
    try { const r = await api(`/generations/${g.id}/favorite`, { method: "POST" }); setSong((s) => ({ ...s, generations: s.generations.map((x) => (x.id === g.id ? { ...x, is_favorite: r.is_favorite } : x)) })); setToast(r.is_favorite ? "Kept" : "Unkept"); }
    catch (e) { setToast(e.message); }
  };
  const removeTake = async (g) => {
    try { await api(`/generations/${g.id}`, { method: "DELETE" }); if (player.isCurrent(g.id)) player.stop(); setSong((s) => ({ ...s, generations: s.generations.filter((x) => x.id !== g.id) })); setToast("Take removed"); }
    catch (e) { setToast(e.message); }
  };
  const rename = async (title) => {
    const t = title.trim(); if (!t || t === song.title) return;
    try { const s = await api(`/songs/${id}`, { method: "PATCH", body: { title: t } }); setSong(s); setToast("Renamed"); } catch (e) { setToast(e.message); }
  };
  const del = async () => {
    try { await api(`/songs/${id}`, { method: "DELETE" }); if (song.generations.some((g) => player.isCurrent(g.id))) player.stop(); router.push("/library"); }
    catch (e) { setToast(e.message); setConfirm(false); }
  };

  if (missing) return <main className="mx-auto max-w-[1100px] px-6 py-10"><p className="text-ink-2">That song isn&apos;t here anymore. <Link href="/library" className="text-acc">Back to Library</Link></p></main>;
  if (!song) return <main className="mx-auto max-w-[1100px] px-6 py-10 text-ink-3">Loading…</main>;

  const batches = takesByBatch(song.generations);
  const all = song.generations.map((g) => trackOf(song, g));
  const first = song.generations.find((g) => g.is_favorite) || batches[0]?.takes[0];
  const sections = parseSections(song.lyrics || "");

  return (
    <main className="mx-auto max-w-[1100px] px-6 pb-28 pt-6">
      <Link href="/library" className="mb-3.5 inline-flex items-center gap-1.5 text-[13px] text-ink-2 hover:text-ink">← Library</Link>
      <div className="mb-5 grid items-end gap-4 md:grid-cols-[120px_1fr_auto]">
        <div className="h-[120px] rounded-[14px]" style={{ background: coverGradient(song.title + song.id) }} />
        <div>
          <h1 contentEditable suppressContentEditableWarning spellCheck={false} aria-label="Song title" onBlur={(e) => rename(e.currentTarget.textContent)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); e.currentTarget.blur(); } }}
            className="-mx-1 rounded-md px-1 font-disp text-[30px] font-extrabold leading-none tracking-tight outline-none focus:bg-sur-2">{song.title}</h1>
          <div className="mt-2 flex flex-wrap gap-1.5">{[song.style.split(",")[0], song.bpm && `${song.bpm} BPM`, song.key, fmtDur(song.duration_s), song.vocal_language.toUpperCase(), `made ${new Date(song.created_at).toLocaleDateString()}`].filter(Boolean).map((t) => <span key={t} className="rounded-[5px] bg-sur-2 px-2 py-0.5 font-mono text-[11px] text-ink-2">{t}</span>)}</div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {first && <button type="button" onClick={() => player.toggle(trackOf(song, first), all)} className="flex items-center gap-2 rounded-r-sm bg-acc px-3.5 py-2 text-[13.5px] font-semibold text-[#1A0C06] hover:bg-acc-2"><PlayIcon playing={player.isCurrent(first.id) && player.now.playing} />Play</button>}
          <button type="button" onClick={moreTakes} disabled={rendering} className="rounded-r-sm border border-line bg-sur-2 px-3.5 py-2 text-[13.5px] font-semibold disabled:opacity-50">{rendering ? "Rendering…" : "2 more takes"}</button>
          <button type="button" onClick={async () => { const g = first; if (!g) return; try { const { upload } = await api(`/uploads/from-generation/${g.id}`, { method: "POST" }); router.push(`/remix?upload=${upload.id}`); } catch (e) { setToast(e.message); } }} className="rounded-r-sm border border-line bg-sur-2 px-3.5 py-2 text-[13.5px] font-semibold">Remix</button>
          <button type="button" onClick={() => setConfirm(true)} className="rounded-r-sm border border-line px-3.5 py-2 text-[13.5px] font-semibold text-acc">Delete</button>
        </div>
      </div>

      {rendering && <div className="mb-4 rounded-[14px] border border-line bg-sur p-4">
        <div className="mb-2 font-mono text-[11px] uppercase tracking-[.1em] text-ink-3">Rendering 2 more takes</div>
        <div className="flex flex-wrap gap-2">{stageRows(job).map((r) => <span key={r.key} className={`rounded-full border px-2.5 py-1 font-mono text-[11px] ${r.state === "done" ? "border-mint text-mint" : r.state === "current" ? "border-acc text-ink" : "border-line text-ink-3"}`}>{r.state === "done" ? "✓ " : ""}{r.label}</span>)}</div>
      </div>}

      <div className="grid gap-4 md:grid-cols-[1fr_340px]">
        <section className="rounded-[14px] border border-line bg-sur p-4" aria-labelledby="takes">
          <h3 id="takes" className="mb-3 flex items-center font-disp text-base font-bold">Takes<span className="ml-auto font-mono text-[11px] text-ink-3">{song.generations.length ? `${song.generations.length} · ${keptCount(song)} kept` : song.status === "rendering" ? "rendering…" : "none yet"}</span></h3>
          {batches.length === 0 && <p className="text-ink-2">{song.status === "rendering" ? "Rendering on your Mac — about a minute." : "No takes yet."}</p>}
          {batches.map((b, bi) => (
            <div key={b.batch_id}>
              <div className="mb-1 mt-3 font-mono text-[10.5px] uppercase tracking-[.08em] text-ink-3">{bi === 0 ? "latest" : "earlier"} · {new Date(b.created_at).toLocaleString([], { hour: "2-digit", minute: "2-digit", month: "short", day: "numeric" })}</div>
              {b.takes.map((g) => {
                const cur = player.isCurrent(g.id), playing = cur && player.now.playing;
                return (
                  <div key={g.id} className={`grid grid-cols-[auto_1fr_auto] items-center gap-3 border-b border-line py-2.5 last:border-b-0 ${cur ? "text-ink" : ""}`}>
                    <button type="button" aria-label={`Play ${takeLabel(g)}`} onClick={() => player.toggle(trackOf(song, g), all)} className={`grid h-[38px] w-[38px] place-items-center rounded-full ${cur ? "bg-acc text-[#1A0C06]" : "bg-ink text-bg"}`}><PlayIcon playing={playing} /></button>
                    <div className="min-w-0">
                      <div className="mb-1 flex justify-between"><span className="font-disp text-sm font-bold">{takeLabel(g)}</span><span className="font-mono text-[10.5px] text-ink-3">seed {g.seed}{g.lufs != null && ` · ${g.lufs.toFixed(1)} LUFS`}</span></div>
                      <Wave url={`${API_URL}${g.mp3_url || g.audio_url}`} height={44} progress={cur ? player.progress : 0} label={`Seek ${takeLabel(g)}`} onSeek={(p) => { if (!cur) player.play(trackOf(song, g), all); player.seek(p); }} />
                    </div>
                    <div className="flex items-center gap-1">
                      <button type="button" aria-pressed={g.is_favorite} aria-label="Keep" onClick={() => keep(g)} className={`rounded-md px-2 py-1.5 text-[15px] ${g.is_favorite ? "text-acc" : "text-ink-3 hover:text-ink"}`}>♥</button>
                      <a href={`${API_URL}${g.mp3_url || g.audio_url}`} download aria-label="Download" className="rounded-md px-2 py-1.5 text-ink-2 hover:bg-sur-3 hover:text-ink">↓</a>
                      <button type="button" aria-label="Remove take" onClick={() => removeTake(g)} className="rounded-md px-2 py-1.5 text-ink-3 hover:bg-sur-3 hover:text-ink">✕</button>
                    </div>
                  </div>);
              })}
            </div>))}
        </section>
        <section className="rounded-[14px] border border-line bg-sur p-4" aria-labelledby="lyrics">
          <h3 id="lyrics" className="mb-3 flex items-center font-disp text-base font-bold">Lyrics<span className="ml-auto font-mono text-[11px] text-ink-3">{song.vocal_language.toUpperCase()}</span></h3>
          {sections.length === 0 ? <p className="text-ink-2">Instrumental.</p> : (
            <div className="max-h-[560px] overflow-auto text-sm leading-relaxed">{sections.map((s, i) => <div key={i} className={i ? "mt-3" : ""}><div className="font-mono text-[11px] text-vio">[{s.tag}]</div><div className="whitespace-pre-wrap">{s.lines.join("\n")}</div></div>)}</div>)}
        </section>
      </div>

      <ConfirmDialog open={confirm} title={`Delete “${song.title}”?`} body="Removes the song, its lyrics and every take from this Mac. There's no undo." onConfirm={del} onCancel={() => setConfirm(false)} />
      {toast && <div role="status" className="fixed bottom-24 left-1/2 z-40 -translate-x-1/2 rounded-full bg-ink px-4 py-2.5 text-[13.5px] font-medium text-bg">{toast}</div>}
    </main>
  );
}

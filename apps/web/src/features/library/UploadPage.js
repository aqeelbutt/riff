"use client";
/** A remixed upload in the Library: the original, its stems and lyrics, and every version you've made of it. */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { API_URL, api } from "@/lib/api";
import { coverGradient, fmtDur } from "@/lib/library";
import { isApproximate, isSynced } from "@/lib/lyricSync";
import { hasSeenCoach } from "@/lib/coach";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Coach, CoachButton } from "@/components/ui/Coach";
import { usePlayerCtx } from "@/features/player/PlayerProvider";
import { LyricSync } from "@/features/player/LyricSync";
import { Wave } from "@/features/player/Wave";
import { useAlign } from "@/features/player/useAlign";
import { LYRIC_SYNC_COACH, lyricSyncSteps } from "@/features/player/lyricSyncCoach";

const PlayIcon = ({ playing }) => playing ? <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h4v14H6zM14 5h4v14h-4z" /></svg> : <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M7 5v14l11-7z" /></svg>;
const Btn = ({ children, className = "", ...p }) => <button type="button" className={`inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-r-sm border border-line bg-sur-2 px-3.5 py-2 text-[13.5px] font-semibold hover:border-line-2 disabled:opacity-50 ${className}`} {...p}>{children}</button>;

function byBatch(remixes) {
  const groups = new Map();
  for (const r of remixes || []) {
    if (!groups.has(r.batch_id)) groups.set(r.batch_id, { batch_id: r.batch_id, created_at: r.created_at, items: [] });
    groups.get(r.batch_id).items.push(r);
  }
  return [...groups.values()].map((g) => ({ ...g, items: [...g.items].sort((a, b) => a.take_index - b.take_index) }))
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
}

export default function UploadPage({ id }) {
  const router = useRouter();
  const player = usePlayerCtx();
  const [up, setUp] = useState(null);
  const [missing, setMissing] = useState(false);
  const [confirm, setConfirm] = useState(null); // {kind, id, title}
  const [toast, setToast] = useState(null);
  const [coach, setCoach] = useState(false);
  useEffect(() => { if (!toast) return; const t = setTimeout(() => setToast(null), 2200); return () => clearTimeout(t); }, [toast]);

  const load = useCallback(() => api(`/uploads/${id}`).then(setUp).catch(() => setMissing(true)), [id]);
  useEffect(() => { load(); }, [load]);
  const { align, busyId } = useAlign({ kind: "remixes", onDone: load });
  // First run: wait until there is something to sync, so the walkthrough never points at an empty page.
  const hasVersions = (up?.remixes || []).some((r) => r.status === "ready");
  useEffect(() => { if (hasVersions && !hasSeenCoach(LYRIC_SYNC_COACH)) setCoach(true); }, [hasVersions]);

  if (missing) return <main className="mx-auto max-w-[1100px] px-6 py-10"><p className="text-ink-2">That upload isn&apos;t here anymore. <Link href="/library" className="text-acc">Back to Library</Link></p></main>;
  if (!up) return <main className="mx-auto max-w-[1100px] px-6 py-10 text-ink-3">Loading…</main>;

  const art = coverGradient(up.title + up.id);
  const orig = { id: `up:${up.id}`, url: `${API_URL}${up.audio_url}`, title: up.title, sub: "Original", art };
  const ready = (up.remixes || []).filter((r) => r.status === "ready");
  const trackOf = (r, i) => ({ id: r.id, url: `${API_URL}${r.mp3_url || r.audio_url}`, title: up.title, sub: `${r.direction || "Remix"}${ready.length > 1 ? ` · ${i + 1}` : ""}`, art });
  const list = [orig, ...ready.map(trackOf)];
  const firstUnsynced = ready.find((r) => !isSynced(r.lyrics_segments))?.id; // the coach points at one button, not every row
  const playingRemix = ready.find((r) => player.isCurrent(r.id));
  const synced = playingRemix && isSynced(playingRemix.lyrics_segments) ? playingRemix.lyrics_segments
    : player.isCurrent(orig.id) && isSynced(up.lyrics_segments) ? up.lyrics_segments : null;

  const keep = async (r) => { try { const res = await api(`/remixes/${r.id}/favorite`, { method: "POST" }); setUp((u) => ({ ...u, remixes: u.remixes.map((x) => (x.id === r.id ? { ...x, is_favorite: res.is_favorite } : x)) })); setToast(res.is_favorite ? "Kept" : "Unkept"); } catch (e) { setToast(e.message); } };
  const del = async () => {
    const c = confirm; setConfirm(null);
    try {
      if (c.kind === "upload") { await api(`/uploads/${up.id}`, { method: "DELETE" }); player.stop(); router.push("/library"); }
      else { await api(`/remixes/${c.id}`, { method: "DELETE" }); if (player.isCurrent(c.id)) player.stop(); load(); setToast("Version removed"); }
    } catch (e) { setToast(e.message); }
  };

  return (
    <main className="mx-auto max-w-[1100px] px-6 pb-28 pt-6">
      <Link href="/library" className="mb-3.5 inline-flex items-center gap-1.5 text-[13px] text-ink-2 hover:text-ink">← Library</Link>
      <div className="mb-5 grid items-end gap-4 md:grid-cols-[120px_1fr_auto]">
        <div className="h-[120px] rounded-[14px]" style={{ background: art }} />
        <div>
          <h1 className="font-disp text-[30px] font-extrabold leading-none tracking-tight">{up.title}</h1>
          <div className="mt-2 flex flex-wrap gap-1.5">{["Your upload", up.bpm && `${Math.round(up.bpm)} BPM`, up.key, fmtDur(up.duration_s), up.vocal_language.toUpperCase(), `${ready.length} version${ready.length === 1 ? "" : "s"}`].filter(Boolean).map((t) => <span key={t} className="rounded-[5px] bg-sur-2 px-2 py-0.5 font-mono text-[11px] text-ink-2">{t}</span>)}</div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Btn className="bg-acc text-[#1A0C06] hover:bg-acc-2" onClick={() => player.toggle(orig, list)}><PlayIcon playing={player.isCurrent(orig.id) && player.now.playing} />Original</Btn>
          <Link href={`/remix?upload=${up.id}`} className="inline-flex items-center rounded-r-sm border border-line bg-sur-2 px-3.5 py-2 text-[13.5px] font-semibold">New version</Link>
          <Btn className="text-acc" onClick={() => setConfirm({ kind: "upload", title: up.title })}>Delete</Btn>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-[1fr_340px]">
        <section data-coach="versions" className="rounded-[14px] border border-line bg-sur p-4" aria-labelledby="versions">
          <h3 id="versions" className="mb-3 flex items-center font-disp text-base font-bold">Versions<span className="ml-auto font-mono text-[11px] text-ink-3">{ready.length ? `${ready.length} · ${ready.filter((r) => r.is_favorite).length} kept` : "none yet"}</span></h3>
          {ready.length === 0 && <p className="text-ink-2">No versions yet. <Link href={`/remix?upload=${up.id}`} className="text-acc">Make one →</Link></p>}
          {byBatch(ready).map((b, bi) => (
            <div key={b.batch_id}>
              <div className="mb-1 mt-3 font-mono text-[10.5px] uppercase tracking-[.08em] text-ink-3">{bi === 0 ? "latest" : "earlier"} · {b.items[0].direction || b.items[0].preset_key || "remix"} · {new Date(b.created_at).toLocaleString([], { hour: "2-digit", minute: "2-digit", month: "short", day: "numeric" })}</div>
              {b.items.map((r) => {
                const i = ready.indexOf(r), t = trackOf(r, i), cur = player.isCurrent(r.id);
                return (
                  <div key={r.id} className="grid grid-cols-[auto_1fr_auto] items-center gap-3 border-b border-line py-2.5 last:border-b-0">
                    <button type="button" aria-label={`Play ${t.sub}`} onClick={() => player.toggle(t, list)} className={`grid h-[38px] w-[38px] place-items-center rounded-full ${cur ? "bg-acc text-[#1A0C06]" : "bg-ink text-bg"}`}><PlayIcon playing={cur && player.now.playing} /></button>
                    <div className="min-w-0">
                      <div className="mb-1 flex justify-between gap-2"><span className="truncate font-disp text-sm font-bold">{r.brief?.title || r.direction || "Remix"}{b.items.length > 1 ? ` · ${r.take_index}` : ""}</span><span className="font-mono text-[10.5px] text-ink-3">{r.mode.replace("_", " ")}{r.lufs != null && ` · ${r.lufs.toFixed(1)} LUFS`}</span></div>
                      <Wave url={`${API_URL}${r.mp3_url || r.audio_url}`} accent height={44} progress={cur ? player.progress : 0} label={`Seek ${t.sub}`} onSeek={(p) => { if (!cur) player.play(t, list); player.seek(p); }} />
                    </div>
                    <div className="flex items-center gap-1">
                      {!isSynced(r.lyrics_segments) && <button type="button" data-coach={r.id === firstUnsynced ? "sync-button" : undefined} title="Time the lyrics to this audio" aria-label={`Sync lyrics for ${t.sub}`} onClick={() => align(r.id)} disabled={busyId === r.id} className="whitespace-nowrap rounded-md border border-line px-2 py-1 text-[11.5px] font-medium text-ink-2 hover:border-line-2 hover:text-ink disabled:opacity-50">{busyId === r.id ? "Listening…" : "Sync to audio"}</button>}
                      <button type="button" aria-pressed={r.is_favorite} aria-label="Keep" onClick={() => keep(r)} className={`rounded-md px-2 py-1.5 text-[15px] ${r.is_favorite ? "text-acc" : "text-ink-3 hover:text-ink"}`}>♥</button>
                      <a href={`${API_URL}${r.mp3_url || r.audio_url}`} download aria-label="Download" className="rounded-md px-2 py-1.5 text-ink-2 hover:bg-sur-3 hover:text-ink">↓</a>
                      <button type="button" aria-label="Remove version" onClick={() => setConfirm({ kind: "remix", id: r.id, title: r.brief?.title || r.direction || "this version" })} className="rounded-md px-2 py-1.5 text-ink-3 hover:bg-sur-3 hover:text-ink">✕</button>
                    </div>
                  </div>);
              })}
            </div>))}
        </section>

        <div className="grid gap-4">
          <section data-coach="lyrics" className="rounded-[14px] border border-line bg-sur p-4" aria-labelledby="lyrics">
            <h3 id="lyrics" className="mb-3 flex items-center gap-2 font-disp text-base font-bold">Lyrics
              <CoachButton onClick={() => setCoach(true)} label="How lyric sync works" />
              <span className="ml-auto font-mono text-[11px] text-ink-3">{synced ? "following the audio" : up.vocal_language.toUpperCase()}</span></h3>
            {synced ? <LyricSync segments={synced} time={player.now.t} live onSeek={(t) => { if (player.now.d) player.seek(t / player.now.d); }} maxHeight={420} />
              : <div className="max-h-[420px] overflow-auto whitespace-pre-wrap text-sm leading-relaxed text-ink-2">{up.lyrics || "No lyrics."}</div>}
          </section>
          {up.stems?.length > 0 && <section className="rounded-[14px] border border-line bg-sur p-4" aria-labelledby="stems">
            <h3 id="stems" className="mb-3 font-disp text-base font-bold">Stems</h3>
            <div className="flex flex-wrap gap-1.5">{up.stems.filter((s) => s.kind !== "instrumental").map((s) => {
              const t = { id: `stem:${up.id}:${s.kind}`, url: `${API_URL}${s.audio_url}`, title: up.title, sub: `${s.kind} stem`, art };
              const on = player.isCurrent(t.id) && player.now.playing;
              return <button key={s.kind} type="button" aria-pressed={on} onClick={() => player.toggle(t)} className={`flex items-center gap-2 rounded-full border px-2.5 py-1.5 text-[12.5px] ${on ? "border-acc text-ink" : "border-line bg-bg-2 text-ink-2"}`}>
                <i className={`h-2 w-2 rounded-full ${{ vocals: "bg-acc", drums: "bg-amber", bass: "bg-vio", other: "bg-mint" }[s.kind]}`} />{s.kind}{s.energy_share != null && <span className="font-mono text-[10.5px] text-ink-3">{Math.round(s.energy_share * 100)}%</span>}</button>;
            })}</div>
          </section>}
        </div>
      </div>

      <Coach name={LYRIC_SYNC_COACH} open={coach} onClose={() => setCoach(false)}
        steps={lyricSyncSteps({ unit: "version", hasApprox: isApproximate(synced) })} />
      <ConfirmDialog open={!!confirm} title={confirm?.kind === "upload" ? `Delete “${confirm?.title}”?` : `Remove “${confirm?.title}”?`}
        body={confirm?.kind === "upload" ? "Removes the upload, its stems and every version from this Mac. There's no undo." : "Removes just this version."}
        confirmLabel={confirm?.kind === "upload" ? "Delete" : "Remove"} onConfirm={del} onCancel={() => setConfirm(null)} />
      {toast && <div role="status" className="fixed bottom-24 left-1/2 z-40 -translate-x-1/2 rounded-full bg-ink px-4 py-2.5 text-[13.5px] font-medium text-bg">{toast}</div>}
    </main>
  );
}

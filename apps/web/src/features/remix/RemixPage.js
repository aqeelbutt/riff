"use client";
/** The Remix screen — mock v2 wired to the API: upload/pick → analysis (stems, tempo, key, lyrics) → style → render → A/B. */
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { API_URL, api } from "@/lib/api";
import { fmtDur, coverGradient } from "@/lib/library";
import { usePlayerCtx } from "@/features/player/PlayerProvider";
import { Wave } from "@/features/player/Wave";
import { MODES, aiLabel, canRemix, closenessLabel, showsVoiceOpts, stageRows, summary, targetBpm } from "./remixFlow";
import { useRemixFlow } from "./useRemixFlow";

const PlayIcon = ({ playing }) => playing ? <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h4v14H6zM14 5h4v14h-4z" /></svg> : <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M7 5v14l11-7z" /></svg>;
const CRUMBS = [["start", "1 · Song"], ["check", "2 · Check"], ["style", "3 · Style"], ["result", "4 · Remix"]];
const crumbIndex = (phase) => ({ start: 0, analyzing: 1, check: 1, style: 2, rendering: 3, result: 3 })[phase] ?? 0;

export default function RemixPage() {
  const params = useSearchParams();
  const f = useRemixFlow({ initialUploadId: params.get("upload") });
  const { state: s, presets } = f;
  const player = usePlayerCtx();
  const [toast, setToast] = useState(null);
  useEffect(() => { if (!toast) return; const t = setTimeout(() => setToast(null), 2400); return () => clearTimeout(t); }, [toast]);
  useEffect(() => { if (s.error) { setToast(s.error); f.clearError(); } }, [s.error]); // eslint-disable-line react-hooks/exhaustive-deps
  const ci = crumbIndex(s.phase);
  return (
    <main className="mx-auto max-w-[1060px] px-6 pb-28 pt-7">
      <nav className="mb-4 flex flex-wrap items-center gap-1.5 font-mono text-[11.5px] uppercase tracking-[.06em] text-ink-3" aria-label="Steps">
        {CRUMBS.map(([k, l], i) => <span key={k} className="contents">{i > 0 && <span>→</span>}<span className={`rounded-full border px-2.5 py-1 ${i === ci ? "border-acc bg-[var(--acc-soft)] text-ink" : i < ci ? "border-transparent bg-[var(--mint-soft)] text-mint" : "border-line"}`}>{l}</span></span>)}
      </nav>
      {s.phase === "start" && <Start f={f} presets={presets} onToast={setToast} player={player} />}
      {s.phase === "analyzing" && <Analyzing f={f} />}
      {s.phase === "check" && <Check f={f} presets={presets} player={player} />}
      {s.phase === "style" && <Style f={f} presets={presets} />}
      {s.phase === "rendering" && <Rendering f={f} presets={presets} />}
      {s.phase === "result" && <Result f={f} presets={presets} player={player} onToast={setToast} />}
      {toast && <div role="status" className="fixed bottom-24 left-1/2 z-40 -translate-x-1/2 rounded-full bg-ink px-4 py-2.5 text-[13.5px] font-medium text-bg">{toast}</div>}
    </main>
  );
}

const Lbl = ({ children, hint }) => <div className="mb-2 flex items-baseline justify-between font-mono text-[11px] uppercase tracking-[.1em] text-ink-3">{children}{hint && <span className="font-sans text-xs normal-case tracking-normal">{hint}</span>}</div>;
const Card = ({ title, right, children, className = "" }) => <section className={`rounded-[14px] border border-line bg-sur p-4 ${className}`}><h3 className="mb-3 flex items-center gap-2 font-disp text-base font-bold">{title}<span className="ml-auto font-mono text-[11px] text-ink-3">{right}</span></h3>{children}</section>;
const Btn = ({ children, primary, danger, className = "", ...p }) => <button type="button" className={`inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-r-sm px-3.5 py-2 text-[13.5px] font-semibold disabled:cursor-not-allowed disabled:opacity-50 ${primary ? "bg-acc text-[#1A0C06] hover:bg-acc-2" : danger ? "border border-line text-acc" : "border border-line bg-sur-2 text-ink hover:border-line-2"} ${className}`} {...p}>{children}</button>;
const Sw = ({ on, onChange, label }) => <button type="button" role="switch" aria-checked={on} aria-label={label} onClick={() => onChange(!on)} className={`relative h-[22px] w-[38px] flex-none rounded-full border border-line-2 transition ${on ? "bg-acc" : "bg-sur-3"}`}><span className={`absolute top-[2px] h-4 w-4 rounded-full transition-all ${on ? "left-[18px] bg-[#1A0C06]" : "left-[2px] bg-ink-2"}`} /></button>;

/* ---------- 1 start ---------- */
function Start({ f, presets, onToast, player }) {
  const [rights, setRights] = useState(false);
  const [lang, setLang] = useState("en");
  const [over, setOver] = useState(false);
  const [songs, setSongs] = useState([]);
  const input = useRef(null);
  useEffect(() => { api("/songs?status=ready").then(setSongs).catch(() => {}); }, []);
  const pick = (file) => { if (!file) return; if (!rights) { onToast("Please confirm it's your song (or you have the rights) first"); return; } f.uploadFile(file, { rights, language: lang }); };
  return (
    <div>
      <h1 className="font-disp text-[30px] font-extrabold leading-none tracking-tight">Remix a song you own</h1>
      <p className="mt-1.5 max-w-[60ch] text-ink-2">Drop in a track. We&apos;ll separate the vocal, find the tempo and key, pull out the lyrics, then rebuild it in any style — keeping your voice, auto-tuned and smooth.</p>
      <div role="button" tabIndex={0} aria-label="Upload a song" onClick={() => input.current?.click()} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.current?.click(); } }}
        onDragEnter={(e) => { e.preventDefault(); setOver(true); }} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files?.[0]); }}
        className={`mt-5 cursor-pointer rounded-2xl border-[1.5px] border-dashed bg-sur px-6 py-12 text-center transition ${over ? "border-acc bg-bg-2" : "border-line-2 hover:border-acc hover:bg-bg-2"}`}>
        <input ref={input} type="file" accept="audio/*,.mp3,.wav,.m4a,.flac,.aac,.ogg" hidden onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />
        <div className="mx-auto mb-3.5 grid h-16 w-16 place-items-center rounded-[18px] border border-line bg-sur-2"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--acc)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 16V4m0 0L7 9m5-5l5 5" /><path d="M4 17v2a1 1 0 001 1h14a1 1 0 001-1v-2" /></svg></div>
        <h2 className="font-disp text-[22px] font-bold">Drop your song here</h2><p className="text-ink-2">or click to choose a file</p>
        <div className="mt-3 font-mono text-[11.5px] text-ink-3">MP3 · WAV · M4A · FLAC · up to 10 minutes</div>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-[1fr_220px]">
        <label className="flex items-start gap-2.5 rounded-r border border-line bg-sur px-3.5 py-3 text-[13.5px] text-ink-2"><input type="checkbox" checked={rights} onChange={(e) => setRights(e.target.checked)} className="mt-[3px] accent-[var(--acc)]" /><span>This is my own recording, or I have the rights to remix it. <span className="text-ink-3">Riff runs on your Mac; nothing is uploaded anywhere.</span></span></label>
        <div><Lbl>Language sung in</Lbl><select value={lang} onChange={(e) => setLang(e.target.value)} aria-label="Language of the vocals" className="w-full rounded-r-sm border border-line bg-sur px-2.5 py-2 text-ink">{presets.languages.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}</select></div>
      </div>
      {songs.length > 0 && <>
        <div className="my-4 flex items-center gap-3 font-mono text-[11px] uppercase tracking-[.1em] text-ink-3"><span className="h-px flex-1 bg-line" />or remix one of your own songs<span className="h-px flex-1 bg-line" /></div>
        <div className="grid gap-2.5" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
          {songs.slice(0, 6).map((sg) => { const g = sg.generations.find((x) => x.is_favorite) || sg.generations[0]; return g && (
            <button key={sg.id} type="button" onClick={() => f.useGeneration(g.id)} className="flex items-center gap-3 rounded-r border border-line bg-sur px-3.5 py-3 text-left hover:border-line-2">
              <span className="h-10 w-10 flex-none rounded-lg" style={{ background: coverGradient(sg.title + sg.id) }} /><span className="min-w-0"><b className="block truncate font-semibold">{sg.title}</b><span className="block truncate text-[12.5px] text-ink-2">{sg.style.split(",")[0]} · {fmtDur(sg.duration_s)} · made in Riff</span></span></button>); })}
        </div></>}
      {f.recent.length > 0 && <>
        <div className="my-4 flex items-center gap-3 font-mono text-[11px] uppercase tracking-[.1em] text-ink-3"><span className="h-px flex-1 bg-line" />recent remixes<span className="h-px flex-1 bg-line" /></div>
        <div className="grid gap-2">
          {f.recent.slice(0, 8).map((u) => <div key={u.id} className="flex flex-wrap items-center gap-3 rounded-r border border-line bg-sur px-3.5 py-2.5">
            <span className="h-9 w-9 flex-none rounded-lg" style={{ background: coverGradient(u.title + u.id) }} /><span className="min-w-0 flex-1"><b className="block truncate font-semibold">{u.title}</b><span className="text-[12px] text-ink-2">{u.status === "analyzed" ? `${Math.round(u.bpm || 0)} BPM · ${u.key || "?"} · ${u.remixes.filter((r) => r.status === "ready").length} remix${u.remixes.filter((r) => r.status === "ready").length === 1 ? "" : "es"}` : u.status}</span></span>
            {u.remixes.filter((r) => r.status === "ready")[0] && <Btn onClick={() => f.openResult(u.id, u.remixes.filter((r) => r.status === "ready")[0].batch_id)}>Open latest</Btn>}
            <Btn onClick={() => f.open(u.id)} disabled={u.status !== "analyzed"}>New remix</Btn>
          </div>)}
        </div></>}
    </div>
  );
}

/* ---------- 2 analyzing / check ---------- */
function Analyzing({ f }) {
  const rows = stageRows(f.state.job);
  return (
    <div>
      <h1 className="font-disp text-[30px] font-extrabold leading-none tracking-tight">Reading “{f.state.upload?.title || "your song"}”</h1>
      <p className="mt-1.5 text-ink-2">Separating the vocal, finding tempo and key, listening for the lyrics. About a minute on this Mac.</p>
      <div className="mt-5 grid max-w-[560px] gap-2">{(rows.length ? rows : [{ key: "queued", label: "Queued", state: "current" }]).map((r) => <div key={r.key} className={`flex items-center gap-3 rounded-r-sm border px-3.5 py-2.5 ${r.state === "current" ? "border-line-2 bg-sur text-ink" : "border-line bg-sur " + (r.state === "done" ? "text-ink-2" : "text-ink-3")}`}><span className={`grid h-[18px] w-[18px] place-items-center rounded-full border-[1.5px] text-[11px] ${r.state === "done" ? "border-mint bg-mint text-[#052]" : r.state === "current" ? "animate-spin border-acc border-t-transparent" : "border-line-2"}`}>{r.state === "done" ? "✓" : ""}</span>{r.label}</div>)}</div>
      <Btn className="mt-4" onClick={f.reset}>Different song</Btn>
    </div>
  );
}

function Check({ f, presets, player }) {
  const u = f.state.upload;
  const [lyrics, setLyrics] = useState(u.lyrics || "");
  useEffect(() => setLyrics(u.lyrics || ""), [u.id, u.lyrics]);
  const src = { id: `up:${u.id}`, url: `${API_URL}${u.audio_url}`, title: u.title, sub: "Original", art: coverGradient(u.title + u.id) };
  const stemTrack = (k) => ({ id: `stem:${u.id}:${k}`, url: `${API_URL}/uploads/${u.id}/stems/${k}`, title: u.title, sub: `${k} stem`, art: src.art });
  const cur = player.isCurrent(src.id);
  return (
    <div>
      <h1 className="font-disp text-[30px] font-extrabold leading-none tracking-tight">Here&apos;s what we heard in “{u.title}”</h1>
      <p className="mt-1.5 text-ink-2">Check the split and the lyrics, fix anything, then pick a style.</p>
      <div className="mt-5 grid gap-4 md:grid-cols-[1.2fr_.8fr]">
        <Card title="Your song" right="ANALYZED">
          <div className="mb-3 flex items-center gap-3"><span className="h-12 w-12 rounded-[10px]" style={{ background: src.art }} /><div><b className="block font-disp text-lg font-bold">{u.title}</b><span className="font-mono text-[11.5px] text-ink-3">{u.filename} · {fmtDur(u.duration_s)}</span></div></div>
          <Wave url={src.url} height={80} progress={cur ? player.progress : 0} label="Original song" onSeek={(p) => { if (!cur) player.play(src); player.seek(p); }} />
          <div className="mt-2.5 flex items-center gap-2"><button type="button" aria-label="Play original" onClick={() => player.toggle(src)} className="grid h-[38px] w-[38px] place-items-center rounded-full bg-ink text-bg"><PlayIcon playing={cur && player.now.playing} /></button><span className="font-mono text-xs text-ink-2">{cur ? fmtDur(player.now.t) : "0:00"} / {fmtDur(u.duration_s)}</span></div>
          <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
            {[["Tempo", `${Math.round(u.bpm || 0)}`, "BPM"], ["Key", u.key || "?", ""], ["Vocals", (u.analysis?.vocals_energy ?? 0) > 0.05 ? "✓ found" : "faint", ""], ["Loudness", `${Math.round(u.lufs ?? 0)}`, "LUFS"]].map(([k, v, unit]) => <div key={k} className="rounded-r-sm bg-bg-2 px-3 py-2.5"><div className="font-mono text-[10.5px] uppercase tracking-[.1em] text-ink-3">{k}</div><div className={`mt-0.5 font-mono text-base font-medium ${v.startsWith("✓") ? "text-mint" : ""}`}>{v} <small className="font-sans text-[11px] text-ink-3">{unit}</small></div></div>)}
          </div>
          <Lbl hint="solo one to check the split"><span className="mt-3.5 inline-block">Stems</span></Lbl>
          <div className="flex flex-wrap gap-1.5">{u.stems.filter((st) => st.kind !== "instrumental").map((st) => { const t = stemTrack(st.kind), on = player.isCurrent(t.id) && player.now.playing; return <button key={st.kind} type="button" aria-pressed={on} onClick={() => player.toggle(t)} className={`flex items-center gap-2 rounded-full border px-2.5 py-1.5 text-[12.5px] ${on ? "border-acc text-ink" : "border-line bg-bg-2 text-ink-2"}`}><i className={`h-2 w-2 rounded-full ${{ vocals: "bg-acc", drums: "bg-amber", bass: "bg-vio", other: "bg-mint" }[st.kind]}`} />{st.kind === "other" ? "Other · keys, guitars, pads" : st.kind[0].toUpperCase() + st.kind.slice(1)}{st.energy_share != null && <span className="font-mono text-[10.5px] text-ink-3">{Math.round(st.energy_share * 100)}%</span>}</button>; })}</div>
        </Card>
        <Card title="Lyrics" right={<select value={u.vocal_language} onChange={(e) => f.patchUpload({ vocal_language: e.target.value })} aria-label="Language" className="rounded-md border border-line bg-bg-2 px-2 py-1 font-sans text-xs text-ink">{presets.languages.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}</select>}>
          <textarea value={lyrics} onChange={(e) => setLyrics(e.target.value)} onBlur={() => { if (lyrics !== (u.lyrics || "")) f.patchUpload({ lyrics }); }} rows={14} aria-label="Lyrics" placeholder="No lyrics heard — type them here if the song has words." className="w-full resize-y rounded-r-sm border border-line bg-bg-2 px-3 py-2.5 text-[14px] leading-relaxed text-ink outline-none focus:border-acc" />
          <div className="mt-2.5 rounded-r-sm border-l-2 border-vio bg-[var(--vio-soft)] px-2.5 py-2 text-[12.5px] text-ink-2">Lyrics are transcribed from your vocal, so the AI can sing backing parts around your own voice, and re-sing them if you ask. Fix a line and it&apos;s used as-is.</div>
        </Card>
      </div>
      <div className="mt-5 flex flex-wrap items-center gap-2.5"><Btn primary onClick={f.toStyle}>Looks right → choose a style</Btn><Btn onClick={f.reset}>Different song</Btn></div>
    </div>
  );
}

/* ---------- 3 style ---------- */
function Style({ f, presets }) {
  const { state: s } = f; const st = s.style; const set = f.setStyle;
  const u = s.upload;
  const bpm = targetBpm(st, u, presets.remix);
  return (
    <div>
      <h1 className="font-disp text-[30px] font-extrabold leading-none tracking-tight">How should it sound?</h1>
      <p className="mt-1.5 text-ink-2">Pick a direction. Every preset keeps your song&apos;s melody and structure; you control how far it travels.</p>
      <div className="mt-3.5 grid gap-2.5" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))" }} role="group" aria-label="Style">
        {presets.remix.map((p) => <button key={p.key} type="button" aria-pressed={st.preset === p.key} onClick={() => set({ preset: p.key, tempo: p.bpm ? st.tempo : "keep" })} className={`relative flex min-h-[104px] flex-col gap-1 rounded-[14px] border p-3.5 text-left transition hover:-translate-y-px ${st.preset === p.key ? "border-acc bg-gradient-to-b from-[var(--acc-soft)] to-transparent" : "border-line bg-sur hover:border-line-2"}`}>
          <b className="font-disp text-base font-bold">{p.label}</b><span className="text-[12.5px] text-ink-2">{p.caption.split(",").slice(1, 3).join(",")}</span><span className="mt-auto font-mono text-[10.5px] text-ink-3">{p.bpm ? `${p.bpm} BPM` : "keeps tempo"}</span>{p.new && <span className="absolute right-2.5 top-2.5 font-mono text-[9.5px] tracking-[.08em] text-mint">NEW</span>}</button>)}
        <button type="button" aria-pressed={st.preset === "custom"} onClick={() => set({ preset: "custom" })} className={`flex min-h-[104px] flex-col items-center justify-center rounded-[14px] border border-dashed p-3.5 text-center ${st.preset === "custom" ? "border-acc bg-[var(--acc-soft)]" : "border-line bg-sur"}`}><b className="font-disp text-base font-bold">Describe it…</b><span className="text-[12.5px] text-ink-2">your own words</span></button>
      </div>
      {st.preset === "custom" && <textarea value={st.custom} onChange={(e) => set({ custom: e.target.value })} rows={2} aria-label="Describe the style" placeholder="e.g. sufi house with harmonium drone, dholak, stacked qawwali backing vocals, 122 BPM" className="mt-3 w-full rounded-r border border-line bg-sur px-3.5 py-3 text-ink outline-none focus:border-acc" />}

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <div>
          <Lbl>Your voice</Lbl>
          <div className="grid auto-cols-fr grid-flow-col gap-[3px] rounded-r-sm border border-line bg-sur p-[3px]" role="group" aria-label="Your voice">
            {MODES.map(([k, l, sub]) => <button key={k} type="button" aria-pressed={st.mode === k} onClick={() => set({ mode: k })} className={`rounded-md px-1.5 py-2 text-[13px] leading-tight ${st.mode === k ? "bg-sur-3 text-ink" : "text-ink-2"}`}>{l}<small className="block text-[10.5px] font-normal text-ink-3">{sub}</small></button>)}
          </div>
          {showsVoiceOpts(st.mode) && <div className="mt-3 grid gap-2">
            <div className="flex items-center justify-between gap-3 rounded-r-sm border border-line bg-sur px-3 py-2.5"><div><b className="block text-[13.5px] font-semibold">Auto-tune</b><span className="text-xs text-ink-2">Smooths your pitch to the song&apos;s key ({u.key || "detected"})</span></div><Sw on={st.autotune} onChange={(v) => set({ autotune: v })} label="Auto-tune" /></div>
            {st.autotune && <div className="px-1"><div className="flex items-center gap-2.5 py-1"><small className="w-16 font-mono text-[10.5px] text-ink-3">Gentle</small><input type="range" min="30" max="100" step="5" value={st.autotuneStrength} onChange={(e) => set({ autotuneStrength: +e.target.value })} aria-label="Auto-tune strength" className="flex-1 accent-[var(--acc)]" /><small className="w-16 text-right font-mono text-[10.5px] text-ink-3">Hard</small></div><div className="text-[12.5px] text-ink-2">{st.autotuneStrength >= 95 ? "Hard-tune — the classic snapped effect" : st.autotuneStrength >= 75 ? "Smooth — corrected, still human" : "Gentle — just nudged toward the key"}</div></div>}
            <div className="flex items-center justify-between gap-3 rounded-r-sm border border-line bg-sur px-3 py-2.5"><div><b className="block text-[13.5px] font-semibold">Harmonies on my voice</b><span className="text-xs text-ink-2">An octave stacked on your lead — off keeps it clean</span></div><Sw on={st.harmony} onChange={(v) => set({ harmony: v })} label="Harmonies on my voice" /></div>
            <div className="flex items-center justify-between gap-3 rounded-r-sm border border-line bg-sur px-3 py-2.5"><div><b className="block text-[13.5px] font-semibold">Vocal chops intro</b><span className="text-xs text-ink-2">Stutter your first phrase over the intro</span></div><Sw on={st.chops} onChange={(v) => set({ chops: v })} label="Vocal chops intro" /></div>
            {st.mode === "hybrid" && <div className="px-1"><Lbl hint="ducked under you while you sing"><span className="mt-2 inline-block">AI vocals</span></Lbl><div className="flex items-center gap-2.5"><small className="w-16 font-mono text-[10.5px] text-ink-3">Behind you</small><input type="range" min="-3" max="4" step="1" value={st.aiForward} onChange={(e) => set({ aiForward: +e.target.value })} aria-label="AI vocals forward or back" className="flex-1 accent-[var(--acc)]" /><small className="w-16 text-right font-mono text-[10.5px] text-ink-3">Forward</small></div><div className="text-[12.5px] text-ink-2">{aiLabel(st.aiForward)}</div></div>}
          </div>}
          <Lbl><span className="mt-4 inline-block">Mood</span></Lbl>
          <div className="flex flex-wrap gap-1.5">{presets.moods.map((m) => <button key={m} type="button" aria-pressed={st.moods.includes(m)} onClick={() => set({ moods: st.moods.includes(m) ? st.moods.filter((x) => x !== m) : [...st.moods, m] })} className={`rounded-full border px-3 py-1.5 text-[13px] ${st.moods.includes(m) ? "border-acc bg-[var(--acc-soft)] text-ink" : "border-line bg-sur text-ink-2"}`}>{m}</button>)}</div>
        </div>
        <div>
          <Lbl>How close to the original</Lbl>
          <div className="flex items-center gap-2.5 py-1"><small className="w-16 font-mono text-[10.5px] text-ink-3">Reinvented</small><input type="range" min="30" max="80" step="5" value={st.closeness} onChange={(e) => set({ closeness: +e.target.value })} aria-label="Closeness to original" className="flex-1 accent-[var(--acc)]" /><small className="w-16 text-right font-mono text-[10.5px] text-ink-3">Faithful</small></div>
          <div className="text-[12.5px] text-ink-2">{closenessLabel(st.closeness)}</div>
          <Lbl><span className="mt-4 inline-block">Tempo</span></Lbl>
          <div className="grid auto-cols-fr grid-flow-col gap-[3px] rounded-r-sm border border-line bg-sur p-[3px]" role="group" aria-label="Tempo">
            {[["keep", "Keep", `${Math.round(u.bpm || 0)} BPM`], ["match", "Match style", (presets.remix.find((p) => p.key === st.preset)?.bpm || Math.round(u.bpm || 0)) + " BPM"], ["custom", "Custom", "…"]].map(([k, l, sub]) => <button key={k} type="button" aria-pressed={st.tempo === k} onClick={() => set({ tempo: k })} className={`rounded-md px-1.5 py-2 text-[13px] leading-tight ${st.tempo === k ? "bg-sur-3 text-ink" : "text-ink-2"}`}>{l}<small className="block text-[10.5px] font-normal text-ink-3">{sub}</small></button>)}
          </div>
          {st.tempo === "custom" && <input type="number" min="40" max="220" value={st.bpmCustom} onChange={(e) => set({ bpmCustom: e.target.value })} aria-label="Custom BPM" placeholder="BPM" className="mt-2 w-32 rounded-r-sm border border-line bg-sur px-3 py-2 font-mono text-ink outline-none focus:border-acc" />}
          {bpm && u.bpm && Math.abs(bpm - u.bpm) > u.bpm * 0.15 && <div className="mt-2 rounded-r-sm border-l-2 border-amber bg-[rgba(245,182,64,.14)] px-2.5 py-2 text-[12.5px] text-ink-2">A tempo change over ~15% stretches your voice audibly. Consider keeping the tempo.</div>}
          <Lbl><span className="mt-4 inline-block">Variations</span></Lbl>
          <div className="grid auto-cols-fr grid-flow-col gap-[3px] rounded-r-sm border border-line bg-sur p-[3px]" role="group" aria-label="Variations">{[1, 2, 3, 4].map((n) => <button key={n} type="button" aria-pressed={st.takes === n} onClick={() => set({ takes: n })} className={`rounded-md px-2 py-1.5 text-[13px] ${st.takes === n ? "bg-sur-3 text-ink" : "text-ink-2"}`}>{n}</button>)}</div>
          <div className="mt-1.5 text-[12.5px] text-ink-2">Different seeds, same settings — pick your favourite. About a minute each.</div>
        </div>
      </div>

      <div className="sticky bottom-24 mt-6 flex flex-wrap items-center gap-3.5 rounded-[14px] border border-line-2 bg-[color-mix(in_srgb,var(--sur)_94%,transparent)] px-3.5 py-3 backdrop-blur-md">
        <div className="min-w-[200px] flex-1 text-[13px] text-ink-2"><b className="text-ink">{summary(s, presets.remix)}</b></div>
        <span className="font-mono text-[11.5px] text-ink-3">about {st.takes} min</span>
        <Btn onClick={f.toCheck}>Back</Btn>
        <Btn primary disabled={!canRemix(s)} onClick={f.remix}><PlayIcon />Remix it</Btn>
      </div>
    </div>
  );
}

/* ---------- 4 rendering / result ---------- */
function Rendering({ f, presets }) {
  const rows = stageRows(f.state.job);
  const n = f.state.style.takes;
  return (
    <div className="mx-auto mt-[5vh] max-w-[600px]">
      <h1 className="font-disp text-[28px] font-extrabold tracking-tight">Remixing “{f.state.upload?.title}”</h1>
      <p className="mt-1 text-[13.5px] text-ink-2">{summary(f.state, presets.remix)}. You&apos;ll get the original and the remix side by side.</p>
      <div className="mt-5 grid gap-2">{(rows.length ? rows : [{ key: "queued", label: "Queued", state: "current" }]).map((r) => <div key={r.key} className={`flex items-center gap-3 rounded-r-sm border px-3.5 py-2.5 ${r.state === "current" ? "border-line-2 bg-sur text-ink" : "border-line bg-sur " + (r.state === "done" ? "text-ink-2" : "text-ink-3")}`}><span className={`grid h-[18px] w-[18px] place-items-center rounded-full border-[1.5px] text-[11px] ${r.state === "done" ? "border-mint bg-mint text-[#052]" : r.state === "current" ? "animate-spin border-acc border-t-transparent" : "border-line-2"}`}>{r.state === "done" ? "✓" : ""}</span>{r.label}{r.key === "rendering" && n > 1 && <span className="ml-auto font-mono text-[11px] text-ink-3">×{n}</span>}</div>)}</div>
      <div className="mt-4 flex items-center justify-between font-mono text-[11.5px] text-ink-3"><span>usually about a minute per variation</span><Btn onClick={f.toStyle}>Back to style</Btn></div>
    </div>
  );
}

function Result({ f, presets, player, onToast }) {
  const { state: s } = f; const u = s.upload;
  const art = coverGradient(u.title + u.id);
  const orig = { id: `up:${u.id}`, url: `${API_URL}${u.audio_url}`, title: u.title, sub: "Original", art };
  const ready = s.batch.filter((r) => r.status === "ready");
  const tracks = ready.map((r, i) => ({ id: r.id, url: `${API_URL}${r.mp3_url || r.audio_url}`, title: u.title, sub: `Remix ${String.fromCharCode(65 + i)} · seed ${r.seed}`, art }));
  const list = [orig, ...tracks];
  const label = (i) => (ready.length > 1 ? `Remix ${String.fromCharCode(65 + i)}` : "Remix");
  const preset = presets.remix.find((p) => p.key === ready[0]?.preset_key);
  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div><h1 className="font-disp text-[30px] font-extrabold leading-none tracking-tight">{u.title} · {preset?.label || "Remix"}</h1>
          <div className="mt-2 flex flex-wrap gap-1.5">{[MODES.find((m) => m[0] === ready[0]?.mode)?.[1], ready[0] && closenessLabel(ready[0].closeness * 100).split(" —")[0], ready[0]?.autotune && "auto-tune", ready[0]?.bpm_to ? `${Math.round(u.bpm)} → ${Math.round(ready[0].bpm_to)} BPM` : `${Math.round(u.bpm || 0)} BPM`, ready[0]?.render_seconds && `${Math.round(ready[0].render_seconds)} s each`].filter(Boolean).map((t) => <span key={t} className="rounded-[5px] bg-sur-2 px-2 py-0.5 font-mono text-[11px] text-ink-2">{t}</span>)}</div></div>
        <div className="flex gap-1.5"><Btn onClick={f.toStyle}>Tweak</Btn><Btn onClick={() => { f.setStyle({}); f.toStyle(); }}>Another style</Btn></div>
      </div>
      {s.batch.some((r) => r.status === "failed") && <div className="mt-3 rounded-r-sm border-l-2 border-acc bg-[var(--acc-soft)] px-3 py-2 text-[13px]">{s.batch.filter((r) => r.status === "failed").length} variation(s) failed: {s.batch.find((r) => r.status === "failed")?.error}</div>}
      <div className="mt-4 grid gap-3.5 md:grid-cols-2">
        {list.map((t, i) => { const cur = player.isCurrent(t.id), r = i ? ready[i - 1] : null; return (
          <div key={t.id} className={`flex flex-col gap-3 rounded-[14px] border bg-sur p-4 transition ${cur ? "border-acc" : "border-line"}`}>
            <div className="flex items-center gap-2.5"><span className="font-disp text-[19px] font-extrabold">{i ? <><i className="mr-2 inline-block h-2 w-2 rounded-full bg-acc align-[2px]" />{label(i - 1)}</> : "Original"}</span><span className="ml-auto font-mono text-[11px] text-ink-3">{i ? `seed ${r.seed}${r.lufs != null ? ` · ${r.lufs.toFixed(1)} LUFS` : ""}` : `${Math.round(u.bpm || 0)} BPM · ${u.key || ""}`}</span></div>
            <Wave url={t.url} accent={!!i} height={72} progress={cur ? player.progress : 0} label={`Seek ${t.sub}`} onSeek={(p) => { if (!cur) player.play(t, list); player.seek(p); }} />
            <div className="flex items-center gap-2"><button type="button" aria-label={`Play ${t.sub}`} onClick={() => player.toggle(t, list)} className="grid h-10 w-10 place-items-center rounded-full bg-ink text-bg hover:bg-white"><PlayIcon playing={cur && player.now.playing} /></button><span className="font-mono text-xs text-ink-2">{cur ? fmtDur(player.now.t) : "0:00"} / {fmtDur(i ? r.duration_s : u.duration_s)}</span>
              {i > 0 && <span className="ml-auto flex gap-1.5"><Btn aria-pressed={r.is_favorite} className={r.is_favorite ? "text-acc" : ""} onClick={async () => { const v = await f.keep(r); onToast(v ? "Kept" : "Unkept"); }}>♥ Keep</Btn><a href={t.url} download className="inline-flex items-center rounded-r-sm border border-line bg-sur-2 px-3.5 py-2 text-[13.5px] font-semibold">Download</a></span>}
            </div>
          </div>); })}
      </div>
      <div className="mt-3.5 flex items-center justify-center gap-2.5 text-[13px] text-ink-2"><Btn onClick={() => { if (list.length > 1) player.switchTo(1); }}>Switch A/B at the same spot</Btn>Tap while playing to compare the same moment.</div>
      <div className="mt-4 flex flex-wrap items-center gap-2.5"><span className="text-[13px] text-ink-2">Not there yet?</span><Btn onClick={() => { f.setStyle({ closeness: Math.min(80, s.style.closeness + 10) }); f.remix(); }}>Closer to the original</Btn><Btn onClick={f.remix}>Another {s.style.takes} variation{s.style.takes === 1 ? "" : "s"}</Btn><span className="flex-1" /><Link href="/library" className="text-ink-2 hover:text-ink">Library</Link><Btn onClick={f.reset}>New song</Btn></div>
    </div>
  );
}

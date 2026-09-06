"use client";
/** The Create screen — the approved mock, wired to the API. Layout: Compose column | Stage; persistent player. */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { EngineBanner } from "@/components/EngineBanner";
import { API_URL } from "@/lib/api";
import { fmt } from "@/features/player/usePlayer";
import { usePlayerCtx } from "@/features/player/PlayerProvider";
import { Wave } from "@/features/player/Wave";
import { canGenerate, canWrite, currentTitle, stageRows } from "./createFlow";
import { useCreateFlow } from "./useCreateFlow";

const EXAMPLES = [
  ["late night drive", "late night drive, neon city, running away together"],
  ["grind & hometown", "grind, hometown, proving them wrong"],
  ["raat aur chaand", "raat, chaand, wo laut aaye — a longing love song"],
  ["rise from the wreckage", "rise from the wreckage, one voice, stadium"],
];
const VOICES = [["female", "Female"], ["male", "Male"], ["duet", "Duet"], ["instrumental", "Instrumental"]];
const ROMAN = new Set(["hi", "ur", "pa", "bn"]);

const SIDE_KEY = "riff:create:side";
const SIDE_COLS = { collapsed: "md:grid-cols-[56px_1fr]", normal: "md:grid-cols-[400px_1fr]", wide: "md:grid-cols-[540px_1fr]" };

export default function CreatePage() {
  const f = useCreateFlow();
  const { state: s, presets } = f;
  const player = usePlayerCtx();
  const [toast, setToast] = useState(null);
  const [side, setSideState] = useState("normal");
  useEffect(() => { try { const v = localStorage.getItem(SIDE_KEY); if (v && SIDE_COLS[v]) setSideState(v); } catch {} }, []);
  const setSide = (v) => { setSideState(v); try { localStorage.setItem(SIDE_KEY, v); } catch {} };
  useEffect(() => { if (!toast) return; const t = setTimeout(() => setToast(null), 2200); return () => clearTimeout(t); }, [toast]);
  useEffect(() => { if (s.error) setToast(s.error); }, [s.error]);

  return (
    <div className={`grid min-h-[calc(100vh-56px)] grid-cols-1 pb-24 ${SIDE_COLS[side]}`}>
      {side === "collapsed" ? <Rail onExpand={() => setSide("normal")} phase={s.phase} /> : <Compose f={f} presets={presets} side={side} setSide={setSide} />}
      <section className="min-w-0 px-4 py-6 md:px-8" aria-live="polite">
        <EngineBanner />
        {s.phase === "compose" && <Empty />}
        {(s.phase === "briefing" || s.phase === "writing" || s.phase === "ready") && <Write f={f} />}
        {s.phase === "rendering" && <Rendering f={f} />}
        {s.phase === "result" && <Result f={f} player={player} onToast={setToast} />}
      </section>
      {toast && <div role="status" className="fixed bottom-24 left-1/2 z-40 -translate-x-1/2 rounded-full bg-ink px-4 py-2.5 text-[13.5px] font-medium text-bg">{toast}</div>}
    </div>
  );
}

/* ---------------- compose ---------------- */
function Lbl({ children, hint }) {
  return <div className="mb-2 flex items-baseline justify-between font-mono text-[11px] uppercase tracking-[.1em] text-ink-3">{children}{hint && <span className="font-sans text-xs normal-case tracking-normal">{hint}</span>}</div>;
}
function Chip({ on, onClick, children, isNew }) {
  return <button type="button" aria-pressed={on} onClick={onClick} className={`rounded-full border px-3 py-1.5 text-[13px] transition ${on ? "border-acc bg-[var(--acc-soft)] text-ink" : "border-line bg-sur text-ink-2 hover:border-line-2 hover:text-ink"}`}>{children}{isNew && <span className="ml-1.5 align-[1px] font-mono text-[9px] tracking-[.08em] text-mint">new</span>}</button>;
}
function Seg({ value, options, onChange }) {
  return <div className="grid auto-cols-fr grid-flow-col gap-[3px] rounded-r-sm border border-line bg-sur p-[3px]">
    {options.map(([v, l]) => <button key={v} type="button" aria-pressed={value === v} onClick={() => onChange(v)} className={`whitespace-nowrap rounded-md px-2 py-1.5 text-[13px] ${value === v ? "bg-sur-3 text-ink" : "text-ink-2 hover:text-ink"}`}>{l}</button>)}
  </div>;
}

function Rail({ onExpand, phase }) {
  return (
    <aside className="hidden flex-col items-center gap-3 border-r border-line bg-bg-2 py-4 md:sticky md:top-14 md:flex md:max-h-[calc(100vh-56px)]">
      <button type="button" onClick={onExpand} aria-label="Expand the song panel" title="Expand" className="grid h-9 w-9 place-items-center rounded-lg border border-line bg-sur text-ink-2 hover:text-ink">›</button>
      <span className="mt-2 [writing-mode:vertical-rl] rotate-180 font-mono text-[11px] uppercase tracking-[.12em] text-ink-3">{phase === "compose" ? "make a song" : "song settings"}</span>
    </aside>
  );
}

function Compose({ f, presets, side, setSide }) {
  const { state: s, compose } = f;
  const c = s.compose;
  const busy = ["briefing", "writing", "rendering"].includes(s.phase);
  return (
    <aside className="flex flex-col gap-5 border-b border-line bg-bg-2 px-5 pb-8 pt-6 md:sticky md:top-14 md:max-h-[calc(100vh-56px)] md:overflow-y-auto md:border-b-0 md:border-r">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1"><h1 className="font-disp text-[26px] font-extrabold leading-tight tracking-tight">Make a song</h1>
          <p className="mt-1 text-[13.5px] text-ink-2">A few words is enough. Claude writes the lyrics, you tweak, the engine sings.</p></div>
        <div className="hidden flex-none gap-1 md:flex" role="group" aria-label="Panel size">
          <button type="button" onClick={() => setSide("collapsed")} aria-label="Collapse the song panel" title="Collapse" className="grid h-8 w-8 place-items-center rounded-lg border border-line bg-sur text-ink-2 hover:text-ink">‹</button>
          <button type="button" onClick={() => setSide(side === "wide" ? "normal" : "wide")} aria-label={side === "wide" ? "Narrow the song panel" : "Widen the song panel"} title={side === "wide" ? "Narrow" : "Widen"} aria-pressed={side === "wide"} className="grid h-8 w-8 place-items-center rounded-lg border border-line bg-sur text-ink-2 hover:text-ink aria-pressed:border-acc aria-pressed:text-ink">⇔</button>
        </div>
      </div>
      <div>
        <Lbl hint="required">What&apos;s it about</Lbl>
        <textarea value={c.keywords} onChange={(e) => compose({ keywords: e.target.value })} rows={3} aria-label="What's the song about" placeholder="late night drive, neon city, running away together"
          onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && canWrite(s)) f.writeLyrics(); }}
          className="w-full resize-y rounded-r border border-line bg-sur px-3.5 py-3 leading-relaxed text-ink placeholder:text-ink-3 focus:border-acc focus:outline-none focus:ring-[3px] focus:ring-[var(--acc-soft)]" />
        <div className="mt-2 flex flex-wrap gap-1.5" aria-label="Examples">
          {EXAMPLES.map(([l, v]) => <button key={l} type="button" onClick={() => compose({ keywords: v })} className="rounded-full border border-dashed border-line-2 px-2 py-1 text-xs text-ink-2 hover:border-solid hover:text-ink">{l}</button>)}
        </div>
      </div>
      <div>
        <Lbl hint="pick one">Style</Lbl>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Style">
          {presets.create.map((p) => <Chip key={p.key} on={(c.style || "pop") === p.key} isNew={p.new} onClick={() => compose({ style: p.key, ...(p.lang ? { language: p.lang } : {}) })}>{p.label}</Chip>)}
        </div>
      </div>
      <div>
        <Lbl>Mood</Lbl>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Mood">
          {presets.moods.map((m) => <Chip key={m} on={c.moods.includes(m)} onClick={() => compose({ moods: c.moods.includes(m) ? c.moods.filter((x) => x !== m) : [...c.moods, m] })}>{m}</Chip>)}
        </div>
      </div>
      <div><Lbl>Voice</Lbl><Seg value={c.vocal} options={VOICES} onChange={(v) => compose({ vocal: v })} /></div>
      <div><Lbl>Language</Lbl>
        <select value={c.language} onChange={(e) => compose({ language: e.target.value })} aria-label="Vocal language" className="w-full rounded-r-sm border border-line bg-sur px-2.5 py-2 text-ink">
          {presets.languages.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
        </select></div>
      {ROMAN.has(c.language) && <div className="rounded-r-sm border-l-2 border-vio bg-[var(--vio-soft)] px-2.5 py-2 text-[12.5px] text-ink-2">Roman script sounds best for this language. Claude writes the lyrics as you&apos;d say them — <em>tere bina</em>, not तेरे बिना.</div>}
      <details className="border-t border-line pt-3">
        <summary className="cursor-pointer text-[13px] text-ink-2">Length, quality &amp; takes</summary>
        <div className="flex flex-col gap-3.5 pt-3.5">
          <div><Lbl>Length</Lbl><Seg value={c.duration_s} options={[[90, "1:30"], [150, "2:30"], [210, "3:30"]]} onChange={(v) => compose({ duration_s: v })} /></div>
          <div><Lbl hint={c.quality === "fast" ? "about 1 min" : "about 3 min"}>Quality</Lbl><Seg value={c.quality} options={[["fast", "Fast"], ["studio", "Studio"]]} onChange={(v) => compose({ quality: v })} /></div>
          <div><Lbl>Takes</Lbl><Seg value={c.takes} options={[[1, "1"], [2, "2"], [4, "4"]]} onChange={(v) => compose({ takes: v })} /></div>
        </div>
      </details>
      <div className="mt-auto pt-2">
        <button type="button" disabled={!canWrite(s)} onClick={f.writeLyrics}
          className="flex w-full items-center justify-center gap-2 rounded-r bg-acc px-4 py-3 text-[14.5px] font-semibold text-[#1A0C06] shadow-[0_8px_24px_-8px_rgba(255,106,61,.6)] transition hover:bg-acc-2 disabled:cursor-not-allowed disabled:bg-sur-3 disabled:text-ink-3 disabled:shadow-none">
          <Sparkle />{busy ? (s.phase === "rendering" ? "Rendering…" : "Writing…") : s.phase === "ready" || s.phase === "result" ? "Rewrite lyrics" : "Write lyrics"}
        </button>
        <div className="mt-2 text-center font-mono text-[11.5px] leading-snug text-ink-3">Claude drafts a brief + full lyrics in a few seconds<span className="hidden xl:inline"> · ⌘↵</span></div>
      </div>
    </aside>
  );
}
const Sparkle = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" /><path d="M19 17l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z" /></svg>;
const PlayIcon = ({ playing }) => playing ? <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h4v14H6zM14 5h4v14h-4z" /></svg> : <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M7 5v14l11-7z" /></svg>;

/* ---------------- stage: empty ---------------- */
function Empty() {
  return (
    <div className="mx-auto mt-[8vh] max-w-[560px] text-center">
      <div className="mx-auto mb-5 grid h-[84px] w-[84px] place-items-center rounded-3xl border border-line bg-gradient-to-br from-sur-2 to-sur"><svg width="38" height="38" viewBox="0 0 24 24" fill="none" stroke="var(--acc)" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true"><path d="M3 12h2l2-6 3 12 3-9 2 5 2-2h4" /></svg></div>
      <h2 className="mb-2 font-disp text-[30px] font-bold tracking-tight">Your song shows up here</h2>
      <p className="mx-auto mb-5 max-w-[44ch] text-ink-2">Type what it&apos;s about, pick a style, and hit <b>Write lyrics</b>. Nothing is rendered until you say so.</p>
      <div className="grid gap-2.5 text-left md:grid-cols-3">
        {[["01 · BRIEF", "Claude proposes a title, tempo, key and structure. Change anything."], ["02 · LYRICS", "Full lyrics in sections. Rewrite one verse without touching the rest."], ["03 · TAKES", "Two takes in about a minute, on your Mac. Keep the one you love."]].map(([b, t]) => (
          <div key={b} className="rounded-r border border-line bg-sur p-3.5"><b className="mb-1.5 block font-mono text-[11px] tracking-[.1em] text-acc">{b}</b><span className="text-[13px] text-ink-2">{t}</span></div>))}
      </div>
    </div>
  );
}

/* ---------------- stage: brief + lyrics ---------------- */
function Skel({ w = "100%" }) { return <div className="h-3.5 animate-pulse rounded-md bg-sur-3" style={{ width: w }} />; }

function Write({ f }) {
  const { state: s } = f;
  const b = s.brief;
  const streaming = s.phase === "writing";
  const sections = streaming ? f.sectionsFromStream : s.sections;
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
        <div><h2 className="font-disp text-[30px] font-extrabold leading-none tracking-tight">{b ? currentTitle(s) : "…"}</h2>
          <div className="mt-1.5 font-mono text-[11.5px] text-ink-3">{b ? `Brief by Claude · ${b.genre} · from “${s.compose.keywords.slice(0, 48)}”` : "Claude is drafting the brief…"}</div></div>
        <button type="button" onClick={f.reset} className="px-2 py-1.5 text-ink-2 hover:text-ink">Start over</button>
      </div>
      <div className="mb-5 grid grid-cols-2 gap-2.5 md:grid-cols-4">
        <div className="col-span-2 rounded-r border border-line bg-sur px-3.5 py-3 md:col-span-4">
          <div className="mb-1.5 font-mono text-[10.5px] uppercase tracking-[.1em] text-ink-3">Title · pick one</div>
          {b ? <div className="flex flex-wrap gap-1.5">{b.titles.map((t, i) => <button key={t} type="button" aria-pressed={s.titleIndex === i} onClick={() => f.pickTitle(i)} className={`rounded-full border px-3 py-1.5 font-disp text-[15px] font-bold ${s.titleIndex === i ? "border-acc bg-[var(--acc-soft)] text-ink" : "border-line text-ink-2"}`}>{t}</button>)}</div> : <Skel w="60%" />}
        </div>
        <Fact k="Genre">{b ? b.genre : <Skel />}</Fact>
        <Fact k="Tempo">{b ? <span className="inline-flex items-center gap-1.5 font-mono"><button type="button" aria-label="Slower" onClick={() => f.patchBrief({ bpm: b.bpm - 2 })} className="h-6 w-6 rounded-md bg-sur-3 text-ink-2">−</button>{b.bpm}<button type="button" aria-label="Faster" onClick={() => f.patchBrief({ bpm: b.bpm + 2 })} className="h-6 w-6 rounded-md bg-sur-3 text-ink-2">+</button><span className="text-[11px] text-ink-3">BPM</span></span> : <Skel />}</Fact>
        <Fact k="Key">{b ? <span className="font-mono">{b.key}</span> : <Skel />}</Fact>
        <Fact k="Mood">{b ? b.mood : <Skel />}</Fact>
        <div className="col-span-2 rounded-r border border-line bg-sur px-3.5 py-3 md:col-span-4">
          <div className="mb-1.5 font-mono text-[10.5px] uppercase tracking-[.1em] text-ink-3">Structure</div>
          {b ? <div className="flex flex-wrap gap-1">{b.structure.map((t, i) => <span key={i} className={`rounded-[5px] px-1.5 py-0.5 font-mono text-[11px] ${/chorus|hook/i.test(t) ? "bg-[var(--vio-soft)] text-vio" : "bg-sur-3 text-ink-2"}`}>{t}</span>)}</div> : <Skel w="70%" />}
        </div>
      </div>

      <div className="overflow-hidden rounded-r border border-line bg-sur">
        <div className="flex items-center justify-between gap-2.5 border-b border-line bg-bg-2 px-3.5 py-2.5">
          <div className="flex items-center gap-2 font-mono text-[11.5px] uppercase tracking-[.08em] text-ink-3"><i className={`h-2 w-2 rounded-full ${s.phase === "ready" ? "bg-mint" : "bg-vio shadow-[0_0_8px_var(--vio)]"}`} />{s.phase === "ready" ? `${s.sections.length} sections · edit any line, or rewrite a section` : streaming ? "Writing lyrics…" : "Waiting for the brief…"}</div>
          <button type="button" onClick={f.writeLyrics} disabled={streaming || !b} className="px-2 py-1 text-ink-2 hover:text-ink disabled:opacity-40">Rewrite all</button>
        </div>
        <div>
          {sections.map((sec, i) => <Section key={`${sec.tag}-${i}`} sec={sec} i={i} f={f} streaming={streaming} last={i === sections.length - 1} />)}
          {s.phase === "briefing" && <div className="p-4"><Skel w="40%" /></div>}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button type="button" disabled={!canGenerate(s)} onClick={f.generate} className="flex items-center gap-2 rounded-r bg-acc px-5 py-3 text-[15px] font-semibold text-[#1A0C06] shadow-[0_8px_24px_-8px_rgba(255,106,61,.6)] hover:bg-acc-2 disabled:cursor-not-allowed disabled:bg-sur-3 disabled:text-ink-3 disabled:shadow-none"><PlayIcon />Generate {s.compose.takes} take{s.compose.takes === 1 ? "" : "s"}</button>
        <span className="font-mono text-[11.5px] text-ink-3">{s.compose.quality === "fast" ? "turbo" : "studio"} · {fmt(s.compose.duration_s)} · {s.compose.takes} take{s.compose.takes === 1 ? "" : "s"} · {s.compose.quality === "fast" ? "about 1 min" : "about 3 min"} · runs on this Mac</span>
      </div>
    </div>
  );
}
function Fact({ k, children }) { return <div className="min-h-[74px] rounded-r border border-line bg-sur px-3.5 py-3"><div className="mb-1.5 font-mono text-[10.5px] uppercase tracking-[.1em] text-ink-3">{k}</div><div className="text-[15px] font-semibold">{children}</div></div>; }

function Section({ sec, i, f, streaming, last }) {
  const busy = !!f.state.busySections[i];
  return (
    <div className={`group relative border-b border-line px-4 py-3.5 last:border-b-0 ${busy ? "opacity-50" : ""}`}>
      <div className="mb-1.5 flex items-center justify-between">
        <span className="font-mono text-[11px] tracking-[.06em] text-vio">[{sec.tag}]</span>
        {!streaming && <span className="flex gap-0.5 opacity-0 transition group-hover:opacity-100 group-focus-within:opacity-100">
          <button type="button" onClick={() => f.rewriteSection(i, "rewrite it fresh, same meaning, better images")} className="rounded-md px-2 py-0.5 text-xs text-ink-2 hover:bg-sur-3 hover:text-ink">↻ Rewrite</button>
          <button type="button" onClick={() => f.rewriteSection(i, "make it shorter — half the lines, keep the best images")} className="rounded-md px-2 py-0.5 text-xs text-ink-2 hover:bg-sur-3 hover:text-ink">Shorter</button>
          <button type="button" onClick={() => f.deleteSection(i)} className="rounded-md px-2 py-0.5 text-xs text-ink-2 hover:bg-sur-3 hover:text-ink">Remove</button></span>}
      </div>
      <div contentEditable={!streaming && !busy} suppressContentEditableWarning spellCheck={false} aria-label={`${sec.tag} lyrics`}
        onBlur={(e) => f.editSection(i, e.currentTarget.innerText)}
        className={`-mx-1 min-h-[1.5em] whitespace-pre-wrap rounded px-1 py-0.5 text-[15px] leading-relaxed outline-none focus:bg-sur-2 ${streaming && last ? "after:animate-pulse after:text-vio after:content-['▍']" : ""}`}>
        {sec.lines.join("\n")}
      </div>
    </div>
  );
}

/* ---------------- stage: rendering ---------------- */
function Rendering({ f }) {
  const { state: s } = f;
  const rows = stageRows(s.job);
  const [t0] = useState(Date.now());
  const [el, setEl] = useState(0);
  useEffect(() => { const t = setInterval(() => setEl(Math.round((Date.now() - t0) / 1000)), 1000); return () => clearInterval(t); }, [t0]);
  const est = s.compose.quality === "fast" ? 60 : 180;
  const doneCount = rows.filter((r) => r.state === "done").length;
  const pct = Math.min(92, rows.length ? (doneCount / rows.length) * 100 + (el / est) * 20 : (el / est) * 90);
  return (
    <div className="mx-auto mt-[6vh] max-w-[600px]">
      <h2 className="font-disp text-[28px] font-extrabold tracking-tight">Rendering “{s.song?.title}”</h2>
      <p className="mb-5 text-[13.5px] text-ink-2">{s.compose.takes} take{s.compose.takes === 1 ? "" : "s"}, different seeds. You can keep editing lyrics for the next run while this plays out.</p>
      <div className="mb-4 h-1.5 overflow-hidden rounded-full bg-sur-2"><i className="block h-full rounded-full bg-gradient-to-r from-acc to-acc-2 transition-[width] duration-500" style={{ width: `${pct}%` }} /></div>
      <div className="grid gap-2">
        {(rows.length ? rows : [{ key: "queued", label: "Queued", state: "current" }]).map((r) => (
          <div key={r.key} className={`flex items-center gap-3 rounded-r-sm border px-3.5 py-2.5 ${r.state === "current" ? "border-line-2 bg-sur text-ink" : r.state === "done" ? "border-line bg-sur text-ink-2" : "border-line bg-sur text-ink-3"}`}>
            <span className={`grid h-[18px] w-[18px] place-items-center rounded-full border-[1.5px] text-[11px] ${r.state === "done" ? "border-mint bg-mint text-[#052]" : r.state === "current" ? "animate-spin border-acc border-t-transparent" : "border-line-2"}`}>{r.state === "done" ? "✓" : ""}</span>{r.label}
          </div>))}
      </div>
      <div className="mt-4 flex items-center justify-between font-mono text-[11.5px] text-ink-3"><span>{el} s elapsed · usually about {est} s</span><button type="button" onClick={f.backToLyrics} className="text-ink-2 hover:text-ink">Back to lyrics</button></div>
    </div>
  );
}

/* ---------------- stage: result ---------------- */
function Result({ f, player, onToast }) {
  const { state: s } = f;
  const router = useRouter();
  const toRemix = async (g) => { try { const { upload } = await api(`/uploads/from-generation/${g.id}`, { method: "POST" }); router.push(`/remix?upload=${upload.id}`); } catch (e) { onToast(e.message); } };
  const url = (g) => `${API_URL}${g.mp3_url || g.audio_url}`;
  const trackOf = (g, i) => ({ id: g.id, url: url(g), title: s.song?.title, sub: `Take ${String.fromCharCode(65 + i)} · seed ${g.seed}` });
  const list = s.takes.map(trackOf);
  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div><h2 className="font-disp text-[30px] font-extrabold leading-none tracking-tight">{s.song?.title}</h2>
          <div className="mt-2 flex flex-wrap gap-1.5">{[s.brief?.genre?.split(" ·")[0], `${s.song?.bpm} BPM`, s.song?.key, fmt(s.song?.duration_s), `${s.compose.quality === "fast" ? "turbo" : "studio"} · ${Math.round(s.takes[0]?.render_seconds || 0)} s`].filter(Boolean).map((t) => <span key={t} className="rounded-[5px] bg-sur-2 px-2 py-0.5 font-mono text-[11px] text-ink-2">{t}</span>)}</div></div>
        <div className="flex gap-1.5"><button type="button" onClick={f.backToLyrics} className="rounded-r-sm border border-line bg-sur-2 px-3 py-1.5 text-[13px]">Edit lyrics</button><button type="button" onClick={f.generate} className="rounded-r-sm border border-line bg-sur-2 px-3 py-1.5 text-[13px]">{s.compose.takes} more take{s.compose.takes === 1 ? "" : "s"}</button></div>
      </div>
      <div className="mt-4 grid gap-3.5 md:grid-cols-2">
        {s.takes.map((g, i) => {
          const u = url(g), on = player.isCurrent(g.id), prog = on ? player.progress : 0;
          return (
            <div key={g.id} className={`flex flex-col gap-3 rounded-[14px] border bg-sur p-4 transition ${on ? "border-acc" : "border-line"}`}>
              <div className="flex items-center gap-2.5"><span className="font-disp text-[19px] font-extrabold">Take {String.fromCharCode(65 + i)}</span><span className="ml-auto font-mono text-[11px] text-ink-3">seed {g.seed}</span>
                <button type="button" aria-pressed={g.is_favorite} aria-label={`Keep take ${i + 1}`} onClick={() => fetch(`${API_URL}/generations/${g.id}/favorite`, { method: "POST" }).then(() => onToast(g.is_favorite ? "Unkept" : "Kept in your Library")).catch(() => {})} className={`h-[30px] w-[30px] rounded-lg ${g.is_favorite ? "text-acc" : "text-ink-3"}`}>♥</button></div>
              <Wave url={u} progress={prog} onSeek={(p) => { if (!on) player.play(trackOf(g, i), list); player.seek(p); }} label={`Seek take ${i + 1}`} />
              <div className="flex items-center gap-2">
                <button type="button" aria-label={`Play take ${i + 1}`} onClick={() => player.toggle(trackOf(g, i), list)} className="grid h-10 w-10 place-items-center rounded-full bg-ink text-bg hover:bg-white"><PlayIcon playing={on && player.now.playing} /></button>
                <span className="font-mono text-xs text-ink-2">{on ? fmt(player.now.t) : "0:00"} / {fmt(g.duration_s)}</span>
                <span className="ml-auto flex gap-1.5">
                  <a href={u} download className="rounded-r-sm border border-line bg-sur-2 px-2.5 py-1.5 text-[12.5px]">Download</a>
                  <button type="button" onClick={() => toRemix(g)} className="rounded-r-sm border border-line bg-sur-2 px-2.5 py-1.5 text-[12.5px]">Remix</button></span>
              </div>
            </div>);
        })}
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2.5"><span className="text-[13px] text-ink-2">Like one? Keep it, then</span><button type="button" onClick={() => s.takes[0] && toRemix(s.takes.find((g) => g.is_favorite) || s.takes[0])} className="rounded-r-sm border border-line bg-sur-2 px-3 py-1.5 text-[13px]">Remix this →</button><span className="flex-1" /><button type="button" onClick={() => { player.stop(); f.reset(); }} className="px-2 py-1.5 text-ink-2 hover:text-ink">New song</button></div>
    </div>
  );
}


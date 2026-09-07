"use client";
/** A short walkthrough that points at real controls: a dimmed page, a ring around the thing being described,
 *  and a callout beside it. Steps name their target with `data-coach="<id>"` on the element itself, so the
 *  coach can't drift from the UI — a renamed target simply has no anchor and that step is skipped.
 *
 *  Placement, the seen-flag and step maths are pure (`lib/coach.js`); this file only measures and renders. */
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { CALLOUT_W, markCoachSeen, placeCallout, spotlightRect, stepAfter } from "@/lib/coach";

const PLAYER_BAR = 84; // the transport is fixed to the bottom; never put a callout under it

export function Coach({ name, steps, open, onClose }) {
  const [i, setI] = useState(0);
  const [live, setLive] = useState(steps); // steps whose target is actually on the page right now
  const [box, setBox] = useState(null); // {spot:{…}, call:{top,left}}
  const callRef = useRef(null);
  const nextRef = useRef(null);

  const close = useCallback(() => { if (name) markCoachSeen(name); onClose?.(); }, [name, onClose]);

  // Resolve targets once per opening. A step whose element isn't rendered (the approximate note before anything
  // has been synced, say) is dropped rather than shown pointing at nothing.
  useEffect(() => {
    if (!open) return;
    const usable = steps.filter((s) => document.querySelector(`[data-coach="${s.anchor}"]`));
    setLive(usable);
    setI(0);
    if (usable.length === 0) close();
  }, [open, steps, close]);

  const step = open ? live[i] : null;

  // Measure after paint so the callout's real height feeds the placement, then keep it pinned on scroll/resize.
  useLayoutEffect(() => {
    if (!step) { setBox(null); return; }
    const el = document.querySelector(`[data-coach="${step.anchor}"]`);
    if (!el) { setBox(null); return; }
    el.scrollIntoView?.({ block: "center", behavior: "smooth" }); // absent in jsdom, and not worth failing over

    const measure = () => {
      const r = el.getBoundingClientRect();
      const anchor = { top: r.top, left: r.left, width: r.width, height: r.height };
      const size = { width: CALLOUT_W, height: callRef.current?.offsetHeight || 190 };
      const frame = { width: window.innerWidth, height: window.innerHeight - PLAYER_BAR };
      setBox({ spot: spotlightRect(anchor), call: placeCallout({ anchor, frame, size, prefer: step.prefer }) });
    };
    measure();
    const t = setTimeout(measure, 340); // after scrollIntoView settles
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => { clearTimeout(t); window.removeEventListener("resize", measure); window.removeEventListener("scroll", measure, true); };
  }, [step]);

  useEffect(() => { if (step) step.onEnter?.(); }, [step]);
  useEffect(() => { if (open) nextRef.current?.focus(); }, [open, i]);

  const go = useCallback((d) => {
    const r = stepAfter(i, d, live.length);
    if (r.done) close(); else setI(r.index);
  }, [i, live.length, close]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === "Escape") { e.preventDefault(); close(); }
      else if (e.key === "ArrowRight") { e.preventDefault(); go(1); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); go(-1); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, go, close]);

  if (!open || !step) return null;
  const last = i === live.length - 1;

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-labelledby="coach-title">
      {box && <div aria-hidden="true" className="pointer-events-none fixed rounded-[11px] outline outline-2 outline-offset-[3px] outline-acc transition-all duration-300"
        style={{ ...box.spot, boxShadow: "0 0 0 9999px rgba(8,9,12,.72)" }} />}
      <div ref={callRef} style={box ? { top: box.call.top, left: box.call.left, maxHeight: box.call.maxHeight } : { opacity: 0 }}
        className="fixed w-[314px] overflow-auto rounded-[13px] border border-line-2 bg-sur-2 p-4 shadow-[0_22px_50px_-16px_rgba(0,0,0,.8)] transition-all duration-300">
        <div className="mb-1.5 font-mono text-[10px] uppercase tracking-[.09em] text-acc">{step.eyebrow || name} · {i + 1} of {live.length}</div>
        <h4 id="coach-title" className="mb-1.5 font-disp text-base font-bold tracking-tight">{step.title}</h4>
        {step.body.map((p, k) => <p key={k} className={`text-[13px] leading-relaxed text-ink-2 ${k ? "mt-2" : ""}`}>{p}</p>)}
        <div className="mt-3.5 flex items-center gap-2">
          <div className="mr-auto flex gap-1.5" aria-hidden="true">
            {live.map((_, k) => <i key={k} className={`h-[5px] w-[5px] rounded-full ${k === i ? "bg-acc" : "bg-sur-3"}`} />)}
          </div>
          <button type="button" onClick={close} className="rounded-lg px-3 py-1.5 text-[12.5px] text-ink-3 hover:text-ink-2">Skip</button>
          {i > 0 && <button type="button" onClick={() => go(-1)} className="rounded-lg border border-line px-3 py-1.5 text-[12.5px] text-ink-2 hover:border-line-2 hover:text-ink">Back</button>}
          <button ref={nextRef} type="button" onClick={() => go(1)} className="rounded-lg bg-acc px-3 py-1.5 text-[12.5px] font-semibold text-[#1A0C06] hover:bg-acc-2">{last ? "Got it" : "Next"}</button>
        </div>
      </div>
    </div>
  );
}

/** The "?" that reopens a walkthrough, sized to sit inside a section heading. */
export function CoachButton({ onClick, label }) {
  return (
    <button type="button" onClick={onClick} title={label} aria-label={label}
      className="grid h-[19px] w-[19px] place-items-center rounded-full border border-line p-0 font-sans text-[11px] leading-none text-ink-3 hover:border-acc hover:text-ink">?</button>
  );
}

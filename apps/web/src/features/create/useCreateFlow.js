"use client";
/** The Create flow hook: the pure reducer + the API calls (brief → streamed lyrics → section rewrites → generate → job → takes). */
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { API_URL, api } from "@/lib/api";
import { parseSections, removeSection, replaceSection } from "@/lib/lyrics";
import { readSSE } from "@/lib/sse";
import { initialState, reduce, songBody } from "./createFlow";
import { useJob } from "./useJob";

export function useCreateFlow() {
  const [state, dispatch] = useReducer(reduce, initialState);
  const [presets, setPresets] = useState({ create: [], moods: [], languages: [] });
  const abortRef = useRef(null);
  const songIdRef = useRef(null);

  useEffect(() => { api("/presets").then(setPresets).catch(() => {}); }, []);

  const { job, track } = useJob({
    songId: state.song?.id || songIdRef.current,
    onDone: async (j) => {
      const sid = songIdRef.current || state.song?.id;
      if (j.status === "done" && sid) {
        try {
          const song = await api(`/songs/${sid}`);
          dispatch({ type: "render_done", job: j, song, takes: song.generations.filter((g) => g.batch_id === song.generations.at(-1)?.batch_id) });
          return;
        } catch (e) { dispatch({ type: "render_failed", job: j, error: e.message }); return; }
      }
      dispatch({ type: "render_failed", job: j, error: j.error ? j.error.split("\n")[0] : `render ${j.status}` });
    },
  });
  useEffect(() => { if (job && state.phase === "rendering") dispatch({ type: "job_update", job }); }, [job, state.phase]);

  const compose = useCallback((patch) => dispatch({ type: "compose", patch }), []);

  const writeLyrics = useCallback(async () => {
    const c = state.compose;
    dispatch({ type: "start_brief" });
    abortRef.current?.abort();
    const ctrl = new AbortController(); abortRef.current = ctrl;
    try {
      const preset = presets.create.find((p) => p.key === c.style);
      const b = await api("/lyrics/brief", { method: "POST", body: {
        keywords: c.keywords, style: preset?.label || c.style || "Pop", style_caption: preset?.caption || null,
        moods: c.moods, vocal: c.vocal, vocal_language: c.language, duration_s: c.duration_s } });
      dispatch({ type: "brief_ready", brief: b.brief, engineCaption: b.engine_caption });
      if (c.vocal === "instrumental") { dispatch({ type: "lyrics_done", lyrics: "", sections: b.brief.structure.map((t) => ({ tag: t, lines: [] })) }); return; }
      const res = await fetch(`${API_URL}/lyrics/write`, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ brief: b.brief, keywords: c.keywords }), signal: ctrl.signal });
      if (!res.ok) throw new Error(`lyrics: ${res.status}`);
      let done = false;
      await readSSE(res, (ev) => {
        if (ev.type === "delta") dispatch({ type: "lyrics_delta", text: ev.text });
        else if (ev.type === "done") { done = true; dispatch({ type: "lyrics_done", lyrics: ev.lyrics, sections: ev.sections }); }
        else if (ev.type === "error") throw new Error(ev.message);
      });
      if (!done) throw new Error("the lyrics stream ended early");
    } catch (e) {
      if (e.name === "AbortError") return;
      dispatch({ type: "error", error: e.message, phase: "compose" });
    }
  }, [state.compose, presets.create]);

  const rewriteSection = useCallback(async (index, instruction) => {
    const secs = state.sections;
    const sec = secs[index]; if (!sec) return;
    dispatch({ type: "section_busy", index, busy: true });
    try {
      const lyrics = secs.map((s) => `[${s.tag}]\n${s.lines.join("\n")}`).join("\n\n");
      const r = await api("/lyrics/section", { method: "POST", body: { lyrics, tag: sec.tag, instruction } });
      dispatch({ type: "sections_set", sections: replaceSection(secs, index, r.lines) });
    } catch (e) { dispatch({ type: "error", error: e.message }); }
    finally { dispatch({ type: "section_busy", index, busy: false }); }
  }, [state.sections]);

  const editSection = useCallback((index, text) => {
    dispatch({ type: "sections_set", sections: replaceSection(state.sections, index, text.split("\n").filter((l) => l.trim())) });
  }, [state.sections]);
  const deleteSection = useCallback((index) => dispatch({ type: "sections_set", sections: removeSection(state.sections, index) }), [state.sections]);
  const pickTitle = useCallback((index) => dispatch({ type: "pick_title", index }), []);
  const patchBrief = useCallback((patch) => dispatch({ type: "brief_patch", patch }), []);

  const generate = useCallback(async () => {
    try {
      const song = await api("/songs", { method: "POST", body: songBody(state) });
      songIdRef.current = song.id;
      const j = await api(`/songs/${song.id}/generate`, { method: "POST", body: { takes: state.compose.takes, quality: state.compose.quality } });
      dispatch({ type: "start_render", song, job: j });
      track(j.id);
    } catch (e) { dispatch({ type: "error", error: e.message }); }
  }, [state, track]);

  const reset = useCallback(() => { abortRef.current?.abort(); songIdRef.current = null; dispatch({ type: "reset" }); }, []);
  const backToLyrics = useCallback(() => dispatch({ type: "back_to_lyrics" }), []);

  return { state, presets, compose, writeLyrics, rewriteSection, editSection, deleteSection, pickTitle, patchBrief, generate, reset, backToLyrics,
           sectionsFromStream: parseSections(state.lyricsText) };
}

"use client";
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { API_URL, api } from "@/lib/api";
import { useJob } from "@/features/create/useJob";
import { initialState, reduce, remixBody } from "./remixFlow";

export function useRemixFlow({ initialUploadId } = {}) {
  const [state, dispatch] = useReducer(reduce, initialState);
  const [presets, setPresets] = useState({ remix: [], reimagine: [], moods: [], languages: [] });
  const [recent, setRecent] = useState([]);
  const uploadIdRef = useRef(null);
  const phaseRef = useRef(state.phase);
  phaseRef.current = state.phase;

  useEffect(() => { api("/presets").then(setPresets).catch(() => {}); }, []);
  const loadRecent = useCallback(() => api("/uploads").then(setRecent).catch(() => {}), []);
  useEffect(() => { loadRecent(); }, [loadRecent]);

  const { job, track } = useJob({
    songId: uploadIdRef.current ? `remix:${uploadIdRef.current}` : null,
    onDone: async (j) => {
      const id = uploadIdRef.current; if (!id) return;
      try {
        const up = await api(`/uploads/${id}`);
        if (phaseRef.current === "analyzing") {
          if (j.status === "done" && up.status === "analyzed") dispatch({ type: "analyzed", upload: up });
          else dispatch({ type: "analysis_failed", error: up.error || (j.error ? j.error.split("\n")[0] : `analysis ${j.status}`) });
        } else {
          const batchId = j.result?.batch_id;
          const batch = up.remixes.filter((r) => !batchId || r.batch_id === batchId);
          if (j.status === "done") dispatch({ type: "render_done", job: j, upload: up, batch });
          else dispatch({ type: "render_failed", job: j, error: batch[0]?.error || (j.error ? j.error.split("\n")[0] : `remix ${j.status}`) });
        }
        loadRecent();
      } catch (e) { dispatch({ type: "error", error: e.message }); }
    },
  });
  useEffect(() => { if (job && (state.phase === "analyzing" || state.phase === "rendering")) dispatch({ type: "job_update", job }); }, [job, state.phase]);

  const open = useCallback(async (uploadId) => {
    try {
      const up = await api(`/uploads/${uploadId}`);
      uploadIdRef.current = up.id;
      if (up.status === "analyzed") dispatch({ type: "analyzed", upload: up });
      else if (up.status === "analyzing" || up.status === "uploaded") { dispatch({ type: "upload_created", upload: up, job: null }); const jobs = await api("/jobs"); const jb = jobs.find((x) => x.kind === "analyze" && x.status !== "done" && JSON.stringify(x).includes(up.id)); if (jb) track(jb.id); }
      else dispatch({ type: "analysis_failed", error: up.error || "analysis failed" });
    } catch (e) { dispatch({ type: "error", error: e.message }); }
  }, [track]);
  useEffect(() => { if (initialUploadId) open(initialUploadId); }, [initialUploadId, open]);

  const uploadFile = useCallback(async (file, { rights, language, title }) => {
    if (!rights) { dispatch({ type: "error", error: "Please confirm it's your song (or you have the rights) first" }); return; }
    dispatch({ type: "uploading" });
    try {
      const fd = new FormData();
      fd.append("file", file); fd.append("rights", "true"); fd.append("vocal_language", language || "en");
      if (title) fd.append("title", title);
      const res = await fetch(`${API_URL}/uploads`, { method: "POST", body: fd });
      if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.detail || `upload failed (${res.status})`); }
      const { upload, job } = await res.json();
      uploadIdRef.current = upload.id;
      dispatch({ type: "upload_created", upload, job });
      track(job.id);
    } catch (e) { dispatch({ type: "analysis_failed", error: e.message }); }
  }, [track]);

  const useGeneration = useCallback(async (genId) => {
    dispatch({ type: "uploading" });
    try {
      const { upload, job } = await api(`/uploads/from-generation/${genId}`, { method: "POST" });
      uploadIdRef.current = upload.id;
      dispatch({ type: "upload_created", upload, job });
      track(job.id);
    } catch (e) { dispatch({ type: "analysis_failed", error: e.message }); }
  }, [track]);

  const patchUpload = useCallback(async (patch) => {
    if (!state.upload) return;
    dispatch({ type: "upload_patch", patch });
    try { await api(`/uploads/${state.upload.id}`, { method: "PATCH", body: patch }); } catch (e) { dispatch({ type: "error", error: e.message }); }
  }, [state.upload]);

  const setStyle = useCallback((patch) => dispatch({ type: "style", patch }), []);
  const toStyle = useCallback(() => dispatch({ type: "to_style" }), []);
  const toCheck = useCallback(() => dispatch({ type: "to_check" }), []);

  const remix = useCallback(async () => {
    if (!state.upload) return;
    try {
      const body = remixBody(state.style, state.upload, presets.remix, presets.reimagine);
      const { remixes, job: j } = await api(`/uploads/${state.upload.id}/remix`, { method: "POST", body });
      dispatch({ type: "start_render", job: j, remixes });
      track(j.id);
    } catch (e) { dispatch({ type: "error", error: e.message }); }
  }, [state.upload, state.style, presets.remix, presets.reimagine, track]);

  const keep = useCallback(async (r) => {
    try { const res = await api(`/remixes/${r.id}/favorite`, { method: "POST" }); dispatch({ type: "open_result", upload: state.upload, batch: state.batch.map((x) => (x.id === r.id ? { ...x, is_favorite: res.is_favorite } : x)) }); return res.is_favorite; }
    catch (e) { dispatch({ type: "error", error: e.message }); }
  }, [state.upload, state.batch]);

  const openResult = useCallback(async (uploadId, batchId) => {
    try { const up = await api(`/uploads/${uploadId}`); uploadIdRef.current = up.id; dispatch({ type: "open_result", upload: up, batch: up.remixes.filter((r) => r.batch_id === batchId) }); }
    catch (e) { dispatch({ type: "error", error: e.message }); }
  }, []);

  const reset = useCallback(() => { uploadIdRef.current = null; dispatch({ type: "reset" }); }, []);

  return { state, presets, recent, uploadFile, useGeneration, open, patchUpload, setStyle, toStyle, toCheck, remix, keep, openResult, reset, clearError: () => dispatch({ type: "error", error: null }) };
}

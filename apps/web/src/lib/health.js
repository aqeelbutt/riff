/** Pure helpers for the status page — unit-tested, framework-free. */

/** Summarize the /health payload into one line per subsystem with a tone (ok | warn | down). */
export function summarizeHealth(h) {
  if (!h) return [{ key: "api", label: "API", tone: "down", detail: "not reachable" }];
  const rows = [{ key: "api", label: "API", tone: "ok", detail: `v${h.version} · ${h.env}` }];
  rows.push({ key: "db", label: "Database", tone: h.db?.ok ? "ok" : "down", detail: h.db?.ok ? "connected" : "not reachable" });
  const e = h.engine || {};
  rows.push({
    key: "engine", label: `Engine · ${e.provider || "?"}`,
    tone: e.ok ? "ok" : "down",
    detail: e.ok ? (e.loaded_model ? `${e.loaded_model}${e.models_initialized ? " · loaded" : " · loads on first song"}` : "ready") : (e.error || "not running"),
  });
  rows.push({ key: "worker", label: "Worker", tone: h.worker?.running ? "ok" : h.worker?.enabled ? "warn" : "down",
    detail: h.worker?.running ? "one GPU lane" : h.worker?.enabled ? "starting" : "disabled" });
  return rows;
}

/** Sort songs newest-first and count takes. */
export function songRows(songs) {
  return [...(songs || [])]
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    .map((s) => ({ id: s.id, title: s.title, status: s.status, takes: (s.generations || []).length, style: s.style }));
}

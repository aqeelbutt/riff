/** Minimal server-sent-events reader over fetch. Calls onEvent(parsedJson) per `data:` line. Returns when the stream ends. */
export async function readSSE(response, onEvent) {
  if (!response.body) throw new Error("no response body");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      for (const ev of parseFrame(frame)) onEvent(ev);
    }
  }
  if (buf.trim()) for (const ev of parseFrame(buf)) onEvent(ev);
}

/** One SSE frame (lines until a blank line) → the JSON payloads of its `data:` lines. Exported for tests. */
export function parseFrame(frame) {
  const out = [];
  for (const line of frame.split("\n")) {
    if (!line.startsWith("data:")) continue;
    const raw = line.slice(5).trim();
    if (!raw) continue;
    try { out.push(JSON.parse(raw)); } catch { out.push({ type: "text", text: raw }); }
  }
  return out;
}

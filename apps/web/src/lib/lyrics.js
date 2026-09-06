/** Lyrics as sections. Mirrors the backend's parse_sections so both sides agree on the tag grammar. */
const TAG_RE = /^\s*\[([^\]]+)\]\s*$/;

export function parseSections(text) {
  const out = [];
  let cur = null;
  for (const raw of (text || "").split("\n")) {
    const m = raw.match(TAG_RE);
    if (m) { cur = { tag: m[1].trim(), lines: [] }; out.push(cur); }
    else if (raw.trim()) {
      if (!cur) { cur = { tag: "Verse 1", lines: [] }; out.push(cur); }
      cur.lines.push(raw.replace(/\s+$/, ""));
    }
  }
  return out;
}

export function serializeSections(sections) {
  return sections.filter((s) => s.tag).map((s) => `[${s.tag}]\n${s.lines.join("\n")}`).join("\n\n") + "\n";
}

/** Replace one section's lines (by index) immutably. */
export function replaceSection(sections, index, lines) {
  return sections.map((s, i) => (i === index ? { ...s, lines } : s));
}

export function removeSection(sections, index) {
  return sections.filter((_, i) => i !== index);
}

/** Is the streamed text currently inside a section (i.e. we've seen at least one tag)? Used for the typing caret. */
export function streamedSections(partialText) {
  const secs = parseSections(partialText);
  return { sections: secs, openTag: secs.length ? secs[secs.length - 1].tag : null };
}

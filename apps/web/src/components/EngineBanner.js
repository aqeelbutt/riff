"use client";
/** A calm, actionable banner when the local engine is down — shown above the screens that need it. */
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { engineNotice } from "@/lib/health";

export function EngineBanner() {
  const [health, setHealth] = useState(undefined); // undefined = not checked yet, null = API unreachable
  useEffect(() => {
    let alive = true;
    const load = () => api("/health").then((h) => alive && setHealth(h)).catch(() => alive && setHealth(null));
    load();
    const t = setInterval(load, 15000);
    return () => { alive = false; clearInterval(t); };
  }, []);
  const notice = engineNotice(health);
  if (!notice) return null;
  return (
    <div role="status" className="mx-auto mb-4 max-w-[1060px] rounded-r border-l-2 border-amber bg-[rgba(245,182,64,.14)] px-3.5 py-3">
      <b className="block text-[13.5px] font-semibold">{notice.title}</b>
      <span className="text-[13px] text-ink-2">{notice.body} </span>
      {notice.command && <code className="rounded bg-bg-2 px-1.5 py-0.5 font-mono text-[12px] text-ink-2">{notice.command}</code>}
    </div>
  );
}

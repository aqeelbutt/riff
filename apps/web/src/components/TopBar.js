"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const NAV = [["/", "Create"], ["/library", "Library"], ["/remix", "Remix"], ["/status", "Status"]];

export function TopBar() {
  const path = usePathname();
  const [engine, setEngine] = useState(null);
  useEffect(() => {
    let alive = true;
    const load = () => api("/health").then((h) => alive && setEngine(h.engine)).catch(() => alive && setEngine({ ok: false }));
    load(); const t = setInterval(load, 15000);
    return () => { alive = false; clearInterval(t); };
  }, []);
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-6 border-b border-line bg-[color-mix(in_srgb,var(--bg)_86%,transparent)] px-5 backdrop-blur-md">
      <Link href="/" className="flex items-center gap-2 font-disp text-[22px] font-extrabold tracking-tight">
        <span className="inline-block h-3 w-3 rotate-45 rounded-[3px] bg-acc shadow-[0_0_0_3px_var(--acc-soft)]" />Riff
      </Link>
      <nav aria-label="Main" className="flex gap-1">
        {NAV.map(([href, label]) => (
          <Link key={href} href={href} aria-current={path === href ? "page" : undefined}
            className={`rounded-full px-3 py-1.5 font-medium ${path === href ? "bg-sur-2 text-ink" : "text-ink-2 hover:text-ink"}`}>{label}</Link>
        ))}
      </nav>
      <div className="ml-auto flex items-center gap-2 rounded-full border border-line px-2.5 py-1 font-mono text-[11.5px] text-ink-2" title="Local music engine">
        <span className={`h-[7px] w-[7px] rounded-full ${engine?.ok ? "bg-mint shadow-[0_0_8px_var(--mint)]" : "bg-acc"}`} />
        {engine ? (engine.ok ? `engine · ${(engine.loaded_model || "turbo").replace("acestep-v15-", "")} · ~1 min / 2 takes` : "engine offline") : "engine …"}
      </div>
    </header>
  );
}

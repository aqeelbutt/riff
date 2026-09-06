"use client";
/** Themed confirm dialog — never a native confirm(). Escape / backdrop cancel; focus lands on the safe button. */
import { useEffect, useRef } from "react";

export function ConfirmDialog({ open, title, body, confirmLabel = "Delete", cancelLabel = "Keep it", danger = true, onConfirm, onCancel }) {
  const cancelRef = useRef(null);
  useEffect(() => {
    if (!open) return;
    cancelRef.current?.focus();
    const onKey = (e) => { if (e.key === "Escape") onCancel?.(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onCancel]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/55 p-5" onClick={(e) => { if (e.target === e.currentTarget) onCancel?.(); }}>
      <div role="dialog" aria-modal="true" aria-labelledby="cd-title" className="w-full max-w-[460px] rounded-2xl border border-line-2 bg-sur p-6">
        <h3 id="cd-title" className="font-disp text-xl font-bold">{title}</h3>
        {body && <p className="mt-2 text-[13.5px] text-ink-2">{body}</p>}
        <div className="mt-4 flex justify-end gap-2">
          <button ref={cancelRef} type="button" onClick={onCancel} className="rounded-r-sm border border-line bg-sur-2 px-3.5 py-2 text-[13.5px] font-semibold">{cancelLabel}</button>
          <button type="button" onClick={onConfirm} className={`rounded-r-sm px-3.5 py-2 text-[13.5px] font-semibold ${danger ? "bg-acc text-[#1A0C06]" : "bg-ink text-bg"}`}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}

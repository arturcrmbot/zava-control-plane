// src/client/components/ExceptionItem.tsx
import type { Exception } from "@shared/types";
import { useState } from "react";

export default function ExceptionItem({ e, selected, onToggle, onResolved }: {
  e: Exception; selected: boolean; onToggle: (id: string) => void;
  onResolved?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const resolveOne = async (action: string) => {
    setBusy(true);
    try {
      await fetch("/api/exceptions/bulk-resolve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          exceptionIds: [e.id],
          resolution: action,
          resolvedBy: "finance-controller@zava",
        }),
      });
      onResolved?.();
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="panel">
      <div className="flex items-start gap-2 p-3">
        <input type="checkbox" className="mt-1" checked={selected} onChange={() => onToggle(e.id)} />
        <button onClick={() => setOpen(!open)} className="flex-1 text-left">
          <div className="flex items-center gap-2 text-sm">
            <span className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-medium text-white ${
              e.severity === "critical" ? "bg-red-600" : e.severity === "high" ? "bg-orange-500" : "bg-amber-500"
            }`}>{e.severity}</span>
            <span className="font-medium text-slate-800">{e.category}</span>
            <span className="text-slate-500 text-xs">· {e.workflowId}</span>
            {e.bulkCandidateIds && e.bulkCandidateIds.length > 1 &&
              <span className="text-xs text-purple-700">bulk×{e.bulkCandidateIds.length}</span>}
          </div>
          <div className="text-xs text-slate-700 mt-1">{e.summary}</div>
          <div className="text-[11px] text-emerald-700 mt-1">→ {e.recommendation}</div>
        </button>
      </div>
      {open && (
        <div className="px-4 pb-3 space-y-2 border-t border-slate-200">
          {e.relatedPolicyRefs.length > 0 && (
            <div>
              <div className="text-[11px] uppercase tracking-wide text-slate-500 mt-2">Policy context</div>
              {e.relatedPolicyRefs.map((p, i) => (
                <div key={i} className="text-xs text-slate-700 mt-1">
                  <div className="font-medium text-slate-800">{p.title}</div>
                  <div className="text-slate-500">{p.snippet}</div>
                  <div className="text-[10px] text-slate-400">{p.source}</div>
                </div>
              ))}
            </div>
          )}
          <div className="flex gap-2 pt-2 flex-wrap">
            {e.options.map((o, i) => (
              <button
                key={i}
                disabled={busy}
                onClick={() => resolveOne(o.action)}
                data-testid={`resolve-${o.action}`}
                className="btn-secondary text-xs py-1 disabled:opacity-40"
              >
                {busy ? <><span className="spinner"/> Resolving…</> : <>{o.label}{o.nonRevocable ? " ⚠" : ""}</>}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

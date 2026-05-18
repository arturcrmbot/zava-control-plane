// web/client/components/feed/BulkActionBar.tsx
//
// Sticky bar shown when the operator is in select mode. Translates the
// selected FeedItem ids ("exception:E1", "hitl:WF-2") back into the raw
// exception ids the bulk-resolve endpoint expects.
import { useState } from "react";

function extractExceptionId(feedItemId: string): string | null {
  // feed item id formats: "exception:<id>" or "hitl:<workflowId>" (no
  // exception). bulk-resolve takes exception ids — HITL items without an
  // associated exception are dropped.
  if (feedItemId.startsWith("exception:")) return feedItemId.slice("exception:".length);
  return null;
}

const ACTIONS = [
  { id: "approved", label: "Approve",      cls: "bg-emerald-600 hover:bg-emerald-700 text-white" },
  { id: "rejected", label: "Reject",       cls: "bg-red-600 hover:bg-red-700 text-white" },
  { id: "request-info", label: "Request docs", cls: "bg-white text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50" },
  { id: "escalate", label: "Escalate L2",  cls: "bg-white text-amber-700 ring-1 ring-amber-300 hover:bg-amber-50" },
];

export default function BulkActionBar({
  selectedIds, onCleared,
}: {
  selectedIds: string[];
  onCleared: () => void;
}) {
  const [busy, setBusy] = useState(false);
  if (selectedIds.length === 0) return null;

  const exceptionIds = selectedIds.map(extractExceptionId).filter((x): x is string => !!x);

  const submit = async (resolution: string) => {
    setBusy(true);
    try {
      await fetch("/api/exceptions/bulk-resolve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          exceptionIds, resolution, resolvedBy: "operator@zava",
        }),
      });
      onCleared();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="sticky bottom-3 z-20 mt-4 mx-auto max-w-3xl bg-slate-900 text-white px-4 py-3 rounded-lg shadow-lg flex items-center gap-3">
      <span className="text-xs">{selectedIds.length} selected</span>
      <span className="text-xs text-slate-400">({exceptionIds.length} bulk-resolvable)</span>
      <div className="ml-auto flex gap-2">
        {ACTIONS.map((a) => (
          <button
            key={a.id}
            type="button"
            disabled={busy || exceptionIds.length === 0}
            onClick={() => void submit(a.id)}
            className={`text-xs px-3 py-1.5 rounded font-medium disabled:opacity-50 ${a.cls}`}
          >{a.label}</button>
        ))}
        <button
          type="button"
          onClick={onCleared}
          className="text-xs px-3 py-1.5 rounded font-medium bg-slate-700 hover:bg-slate-600 text-white"
        >Cancel</button>
      </div>
    </div>
  );
}

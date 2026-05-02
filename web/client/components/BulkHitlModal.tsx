// src/client/components/BulkHitlModal.tsx
import { useState } from "react";

export default function BulkHitlModal({ ids, onClose, onConfirm }: {
  ids: string[]; onClose: () => void; onConfirm: (resolution: string) => void;
}) {
  const [busy, setBusy] = useState(false);

  const handleConfirm = async (resolution: string) => {
    setBusy(true);
    try {
      await onConfirm(resolution);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/40 flex items-center justify-center z-50">
      <div className="bg-white border border-slate-200 rounded-lg shadow-xl p-5 w-[480px] space-y-3">
        <div className="font-semibold text-slate-900">Bulk resolve {ids.length} exception{ids.length === 1 ? "" : "s"}</div>
        <div className="text-xs text-slate-600 max-h-40 overflow-auto font-mono bg-slate-50 border border-slate-200 rounded p-2">
          {ids.map(id => <div key={id}>{id}</div>)}
        </div>
        <div className="flex gap-2 justify-end">
          <button onClick={onClose} disabled={busy} className="btn-secondary text-xs py-1 disabled:opacity-40">Cancel</button>
          <button disabled={busy} onClick={() => handleConfirm("approved")} className="text-xs px-3 py-1.5 rounded-md bg-emerald-600 text-white font-medium hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed">
            {busy ? <><span className="spinner"/> Approving…</> : "Approve all"}
          </button>
          <button disabled={busy} onClick={() => handleConfirm("rejected")} className="text-xs px-3 py-1.5 rounded-md bg-red-600 text-white font-medium hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed">
            {busy ? <><span className="spinner"/> Rejecting…</> : "Reject all"}
          </button>
        </div>
      </div>
    </div>
  );
}

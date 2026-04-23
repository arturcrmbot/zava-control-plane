// src/client/components/BulkHitlModal.tsx
export default function BulkHitlModal({ ids, onClose, onConfirm }: {
  ids: string[]; onClose: () => void; onConfirm: (resolution: string) => void;
}) {
  return (
    <div className="fixed inset-0 bg-slate-900/40 flex items-center justify-center z-50">
      <div className="bg-white border border-slate-200 rounded-lg shadow-xl p-5 w-[480px] space-y-3">
        <div className="font-semibold text-slate-900">Bulk resolve {ids.length} exception{ids.length === 1 ? "" : "s"}</div>
        <div className="text-xs text-slate-600 max-h-40 overflow-auto font-mono bg-slate-50 border border-slate-200 rounded p-2">
          {ids.map(id => <div key={id}>{id}</div>)}
        </div>
        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="btn-secondary text-xs py-1">Cancel</button>
          <button onClick={() => onConfirm("approved")} className="text-xs px-3 py-1.5 rounded-md bg-emerald-600 text-white font-medium hover:bg-emerald-700">Approve all</button>
          <button onClick={() => onConfirm("rejected")} className="text-xs px-3 py-1.5 rounded-md bg-red-600 text-white font-medium hover:bg-red-700">Reject all</button>
        </div>
      </div>
    </div>
  );
}

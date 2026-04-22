// src/client/components/BulkHitlModal.tsx
export default function BulkHitlModal({ ids, onClose, onConfirm }: {
  ids: string[]; onClose: () => void; onConfirm: (resolution: string) => void;
}) {
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-slate-900 border border-slate-700 rounded p-4 w-[480px] space-y-3">
        <div className="font-semibold">Bulk resolve {ids.length} exception{ids.length === 1 ? "" : "s"}</div>
        <div className="text-xs text-slate-400 max-h-40 overflow-auto">
          {ids.map(id => <div key={id}>{id}</div>)}
        </div>
        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="text-xs px-3 py-1.5 border border-slate-700 rounded">Cancel</button>
          <button onClick={() => onConfirm("approved")} className="text-xs px-3 py-1.5 bg-emerald-600 rounded hover:bg-emerald-500">Approve all</button>
          <button onClick={() => onConfirm("rejected")} className="text-xs px-3 py-1.5 bg-red-600 rounded hover:bg-red-500">Reject all</button>
        </div>
      </div>
    </div>
  );
}

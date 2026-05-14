// src/client/routes/ExceptionQueue.tsx
import { useState } from "react";
import { useExceptions } from "../hooks/useExceptions";
import ExceptionItem from "../components/ExceptionItem";
import BulkHitlModal from "../components/BulkHitlModal";

export default function ExceptionQueue() {
  const { items, refresh } = useExceptions();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [modal, setModal] = useState(false);

  const toggle = (id: string) => {
    const n = new Set(selected);
    n.has(id) ? n.delete(id) : n.add(id);
    setSelected(n);
  };

  const confirm = async (resolution: string) => {
    await fetch("/api/exceptions/bulk-resolve", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ exceptionIds: [...selected], resolution, resolvedBy: "finance-controller@zava" })
    });
    setSelected(new Set());
    setModal(false);
    await refresh();
  };

  return (
    <div className="space-y-4">
      <div className="flex items-baseline gap-3">
        <div className="text-lg font-semibold text-slate-900">Exception Queue</div>
        <div className="text-xs text-slate-500">{items.length} open</div>
        <div className="ml-auto flex gap-2">
          <button disabled={selected.size === 0} onClick={() => setModal(true)}
            className="btn-primary text-xs py-1.5 disabled:opacity-40">
            Bulk resolve ({selected.size})
          </button>
        </div>
      </div>
      <div className="space-y-2">
        {items.length === 0 && (
          <div className="panel panel-body text-sm text-slate-500 italic">No open exceptions.</div>
        )}
        {items.map(e => (
          <ExceptionItem
            key={e.id}
            e={e}
            selected={selected.has(e.id)}
            onToggle={toggle}
            onResolved={refresh}
          />
        ))}
      </div>
      {modal && <BulkHitlModal ids={[...selected]} onClose={() => setModal(false)} onConfirm={confirm} />}
    </div>
  );
}

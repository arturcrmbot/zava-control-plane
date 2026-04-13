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
      body: JSON.stringify({ exceptionIds: [...selected], resolution, resolvedBy: "finance-controller@wpp" })
    });
    setSelected(new Set());
    setModal(false);
    await refresh();
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <div className="text-sm font-semibold">Exception Queue</div>
        <div className="text-xs text-slate-500">{items.length} open</div>
        <div className="ml-auto flex gap-2">
          <button disabled={selected.size === 0} onClick={() => setModal(true)}
            className="text-xs px-3 py-1.5 bg-amber-600 rounded hover:bg-amber-500 disabled:opacity-40">
            Bulk resolve ({selected.size})
          </button>
        </div>
      </div>
      <div className="space-y-2">
        {items.map(e => <ExceptionItem key={e.id} e={e} selected={selected.has(e.id)} onToggle={toggle} />)}
      </div>
      {modal && <BulkHitlModal ids={[...selected]} onClose={() => setModal(false)} onConfirm={confirm} />}
    </div>
  );
}

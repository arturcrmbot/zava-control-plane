// web/client/components/apex/InterventionProtocols.tsx
import { useState } from "react";
import type { Exception } from "@shared/types";

export default function InterventionProtocols({ exception, onResolved }: {
  exception: Exception; onResolved?: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const act = async (action: string) => {
    setBusy(true);
    try {
      await fetch("/api/exceptions/bulk-resolve", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          exceptionIds: [exception.id],
          resolution: action,
          resolvedBy: "finance-controller@zava",
        }),
      });
      onResolved?.();
    } finally { setBusy(false); }
  };
  return (
    <div className="panel" data-testid="intervention-protocols">
      <div className="panel-header">Intervention Protocols</div>
      <div className="panel-body grid grid-cols-2 gap-2">
        {exception.options.map(o => (
          <button key={o.action}
                  disabled={busy}
                  onClick={() => act(o.action)}
                  data-testid={`protocol-${o.action}`}
                  className={o.recommended ? "btn-primary" :
                             o.action === "reject" ? "btn-danger" : "btn-secondary"}>
            {o.recommended && <span className="text-[10px] uppercase tracking-wider bg-white dark:bg-slate-900/20 rounded px-1">recommended</span>}
            {o.label}{o.nonRevocable ? " ⚠" : ""}
          </button>
        ))}
      </div>
    </div>
  );
}

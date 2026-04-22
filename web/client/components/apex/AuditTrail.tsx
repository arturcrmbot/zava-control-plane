// web/client/components/apex/AuditTrail.tsx
import type { ActionLedgerEntry } from "@shared/types";

export default function AuditTrail({ ledger }: { ledger: ActionLedgerEntry[] }) {
  const last = ledger.slice(-8).reverse();
  return (
    <div className="panel" data-testid="audit-trail">
      <div className="panel-header flex items-center justify-between">
        <span>Audit Trail</span>
        <span className="text-[11px] font-normal text-slate-500">last {last.length}</span>
      </div>
      <div className="panel-body space-y-1.5">
        {last.length === 0 && <div className="text-xs text-slate-500">no entries yet</div>}
        {last.map((e, i) => (
          <div key={i} className="text-xs">
            <div className="text-slate-800 font-medium">{e.action}</div>
            <div className="text-slate-500">
              {new Date(e.timestamp * 1000).toLocaleString()} · {e.actorKind}:{e.actorId}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

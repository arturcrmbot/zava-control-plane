// web/client/components/apex/AuditTrail.tsx
import type { ActionLedgerEntry } from "@shared/types";

export default function AuditTrail({
  ledger, blobUrl,
}: {
  ledger: ActionLedgerEntry[];
  blobUrl?: string | null;
}) {
  const last = ledger.slice(-8).reverse();
  return (
    <div className="panel" data-testid="audit-trail">
      <div className="panel-header flex items-center justify-between">
        <span>Audit Trail</span>
        <span className="text-[11px] font-normal text-slate-500 dark:text-slate-400">last {last.length}</span>
      </div>
      <div className="panel-body space-y-1.5">
        {last.length === 0 && <div className="text-xs text-slate-500 dark:text-slate-400">no entries yet</div>}
        {last.map((e, i) => (
          <div key={i} className="text-xs">
            <div className="text-slate-800 dark:text-slate-100 font-medium">{e.action}</div>
            <div className="text-slate-500 dark:text-slate-400">
              {new Date(e.timestamp * 1000).toLocaleString()} · {e.actorKind}:{e.actorId}
            </div>
          </div>
        ))}
        {blobUrl ? (
          <div className="pt-2 mt-2 border-t border-slate-200 dark:border-slate-700">
            <a
              href={blobUrl}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-blue-700 dark:text-blue-300 hover:underline inline-flex items-center gap-1"
              title="Immutable append-blob on Azure Storage (version-level immutability enabled)"
            >
              Open immutable audit ledger →
            </a>
            <div className="text-[10px] text-slate-400 dark:text-slate-500 mt-0.5">
              every entry above is also appended to this blob
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

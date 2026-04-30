// web/client/components/apex/KpiTileRow.tsx
import type { Workflow } from "@shared/types";

export default function KpiTileRow({ workflows, exceptionsCount }: {
  workflows: Workflow[]; exceptionsCount: number;
}) {
  const inFlight = workflows.filter(w => w.status === "in_progress");
  const expenseCount = inFlight.filter(w => w.type === "expense-claim").length;
  const hiringCount = inFlight.filter(w => w.type === "hiring").length;
  const split = (expenseCount > 0 || hiringCount > 0)
    ? `${expenseCount} expense · ${hiringCount} hiring`
    : null;

  const tiles: Array<{ label: string; v: number; sub?: string | null }> = [
    { label: "In flight", v: inFlight.length, sub: split },
    { label: "Awaiting review", v: workflows.filter(w => w.status === "awaiting_hitl").length },
    { label: "Completed",   v: workflows.filter(w => w.status === "completed").length },
    { label: "Failed",      v: workflows.filter(w => w.status === "failed").length },
    { label: "Open exceptions",  v: exceptionsCount },
  ];
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 min-w-0" data-testid="kpi-tile-row">
      {tiles.map(t => (
        <div key={t.label} className="panel panel-body min-w-0">
          <div className="text-[11px] uppercase tracking-wide text-slate-500 leading-tight">{t.label}</div>
          <div className="text-2xl font-semibold text-slate-900 mt-1">{t.v}</div>
          {t.sub && <div className="text-[10px] text-slate-500 mt-0.5">{t.sub}</div>}
        </div>
      ))}
    </div>
  );
}

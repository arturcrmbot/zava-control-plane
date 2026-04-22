// web/client/components/apex/KpiTileRow.tsx
import type { Workflow } from "@shared/types";

export default function KpiTileRow({ workflows, exceptionsCount }: {
  workflows: Workflow[]; exceptionsCount: number;
}) {
  const tiles = [
    { label: "Active Runs", v: workflows.filter(w => w.status === "in_progress").length },
    { label: "Awaiting HITL", v: workflows.filter(w => w.status === "awaiting_hitl").length },
    { label: "Completed",   v: workflows.filter(w => w.status === "completed").length },
    { label: "Failed",      v: workflows.filter(w => w.status === "failed").length },
    { label: "Exceptions",  v: exceptionsCount },
  ];
  return (
    <div className="grid grid-cols-5 gap-3" data-testid="kpi-tile-row">
      {tiles.map(t => (
        <div key={t.label} className="panel panel-body">
          <div className="text-[10px] uppercase tracking-wide text-slate-500">{t.label}</div>
          <div className="text-2xl font-semibold text-slate-900 mt-1">{t.v}</div>
        </div>
      ))}
    </div>
  );
}

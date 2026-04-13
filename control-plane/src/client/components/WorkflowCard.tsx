// src/client/components/WorkflowCard.tsx
import type { Workflow } from "@shared/types";
import { Link } from "react-router-dom";
import { PHASE_ORDER } from "@shared/types";

const statusColor: Record<Workflow["status"], string> = {
  in_progress: "text-blue-400", awaiting_hitl: "text-amber-400",
  completed: "text-emerald-400", failed: "text-red-400"
};

export default function WorkflowCard({ w }: { w: Workflow }) {
  const phaseIdx = PHASE_ORDER.indexOf(w.currentPhase);
  const pct = ((phaseIdx + 1) / PHASE_ORDER.length) * 100;
  return (
    <Link to={`/workflows/${w.id}`} className="block border border-slate-800 rounded p-3 hover:border-slate-700 bg-slate-900/50">
      <div className="flex items-center justify-between">
        <div className="font-medium text-sm">{w.id}</div>
        <div className={`text-[10px] uppercase ${statusColor[w.status]}`}>{w.status}</div>
      </div>
      <div className="text-xs text-slate-400 mt-0.5 truncate">{w.vendor.name}</div>
      <div className="text-xs text-slate-300 mt-1">
        {w.invoice.currency} {w.invoice.amount.toLocaleString()}
      </div>
      <div className="mt-2 text-[10px] text-slate-500">{w.currentPhase}</div>
      <div className="h-1 bg-slate-800 rounded mt-1">
        <div className="h-1 bg-blue-400 rounded" style={{ width: `${pct}%` }} />
      </div>
      {w.activeExceptionId && (
        <div className="mt-2 text-[10px] text-amber-400">⚠ exception</div>
      )}
    </Link>
  );
}

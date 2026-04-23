// src/client/components/WorkflowCard.tsx
import type { Workflow } from "@shared/types";
import { Link } from "react-router-dom";
import { PHASE_ORDER } from "@shared/types";

const statusColor: Record<Workflow["status"], string> = {
  in_progress: "text-blue-700", awaiting_hitl: "text-amber-700",
  completed: "text-emerald-700", failed: "text-red-700"
};

export default function WorkflowCard({ w }: { w: Workflow }) {
  const phaseIdx = PHASE_ORDER.indexOf(w.currentPhase);
  const pct = ((phaseIdx + 1) / PHASE_ORDER.length) * 100;
  return (
    <Link to={`/workflows/${w.id}`} className="block bg-white border border-slate-200 rounded-lg p-3 shadow-sm hover:border-blue-300 hover:shadow transition">
      <div className="flex items-center justify-between">
        <div className="font-medium text-sm text-slate-900">{w.id}</div>
        <div className={`text-[10px] uppercase tracking-wide font-medium ${statusColor[w.status]}`}>{w.status}</div>
      </div>
      <div className="text-xs text-slate-500 mt-0.5 truncate">{w.vendor.name}</div>
      <div className="text-xs text-slate-700 mt-1 font-medium">
        {w.invoice.currency} {w.invoice.amount.toLocaleString()}
      </div>
      <div className="mt-2 text-[10px] text-slate-500">{w.currentPhase}</div>
      <div className="h-1 bg-slate-100 rounded mt-1">
        <div className="h-1 bg-blue-500 rounded" style={{ width: `${pct}%` }} />
      </div>
      {w.activeExceptionId && (
        <div className="mt-2 text-[10px] text-amber-700 font-medium">⚠ exception</div>
      )}
    </Link>
  );
}

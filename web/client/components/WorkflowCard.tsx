// src/client/components/WorkflowCard.tsx
import type { Workflow } from "@shared/types";
import { Link } from "react-router-dom";
import { PHASE_ORDER, EXPENSE_PHASE_ORDER } from "@shared/types";

const statusColor: Record<Workflow["status"], string> = {
  in_progress: "text-blue-700", awaiting_hitl: "text-amber-700",
  completed: "text-emerald-700", failed: "text-red-700"
};

const verdictColor: Record<NonNullable<Workflow["verdict"]>, string> = {
  green: "text-emerald-700 bg-emerald-50",
  amber: "text-amber-700 bg-amber-50",
  red: "text-red-700 bg-red-50",
};

export default function WorkflowCard({ w }: { w: Workflow }) {
  const phaseOrder = w.type === "expense-claim" ? EXPENSE_PHASE_ORDER : PHASE_ORDER;
  const phaseIdx = phaseOrder.indexOf(w.currentPhase);
  const pct = ((phaseIdx + 1) / phaseOrder.length) * 100;
  const subtitle = w.claim ? w.claim.employeeId : w.vendor?.name ?? w.id;
  const amount = w.claim ?? w.invoice;
  return (
    <Link to={`/workflows/${w.id}`} className="block bg-white border border-slate-200 rounded-lg p-3 shadow-sm hover:border-blue-300 hover:shadow transition">
      <div className="flex items-center justify-between">
        <div className="font-medium text-sm text-slate-900">{w.id}</div>
        <div className={`text-[10px] uppercase tracking-wide font-medium ${statusColor[w.status]}`}>{w.status}</div>
      </div>
      <div className="text-xs text-slate-500 mt-0.5 truncate">{subtitle}</div>
      {amount && (
        <div className="text-xs text-slate-700 mt-1 font-medium flex items-center gap-2">
          <span>{amount.currency} {amount.amount.toLocaleString()}</span>
          {w.claim && (
            <span className="text-[10px] text-slate-500 capitalize">{w.claim.category}</span>
          )}
          {w.verdict && (
            <span className={`text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded ${verdictColor[w.verdict]}`}>
              {w.verdict}
            </span>
          )}
        </div>
      )}
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

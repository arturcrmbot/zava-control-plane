// src/client/components/WorkflowCard.tsx
import type { Workflow } from "@shared/types";
import { Link } from "react-router-dom";
import { PHASE_ORDER, EXPENSE_PHASE_ORDER } from "@shared/types";
import { AlertTriangle, Clock } from "lucide-react";

const STATUS_COLOR: Record<Workflow["status"], string> = {
  in_progress: "bg-blue-50 text-blue-700 ring-1 ring-blue-200",
  awaiting_hitl: "bg-amber-50 text-amber-700 ring-1 ring-amber-200",
  completed: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
  failed: "bg-red-50 text-red-700 ring-1 ring-red-200",
};

const STATUS_LABEL: Record<Workflow["status"], string> = {
  in_progress: "in flight",
  awaiting_hitl: "needs review",
  completed: "done",
  failed: "failed",
};

const VERDICT_COLOR: Record<NonNullable<Workflow["verdict"]>, string> = {
  green: "bg-emerald-100 text-emerald-700",
  amber: "bg-amber-100 text-amber-700",
  red: "bg-red-100 text-red-700",
};

const PROGRESS_BAR: Record<Workflow["status"], string> = {
  in_progress: "bg-blue-500",
  awaiting_hitl: "bg-amber-500",
  completed: "bg-emerald-500",
  failed: "bg-red-500",
};

function fmtSlaRemaining(slaDueAt: number): { text: string; warn: boolean } | null {
  const remainSec = slaDueAt - Date.now() / 1000;
  if (remainSec < 0) return { text: "SLA breached", warn: true };
  const remainHr = remainSec / 3600;
  if (remainHr < 1) return { text: `${Math.round(remainSec / 60)}m left`, warn: true };
  if (remainHr < 4) return { text: `${remainHr.toFixed(1)}h left`, warn: true };
  return null;
}

export default function WorkflowCard({ w }: { w: Workflow }) {
  const phaseOrder = w.type === "expense-claim" ? EXPENSE_PHASE_ORDER : PHASE_ORDER;
  const phaseIdx = phaseOrder.indexOf(w.currentPhase);
  const pct = ((phaseIdx + 1) / phaseOrder.length) * 100;
  const subtitle = w.claim
    ? `${w.claim.employeeId} · ${w.claim.vendor}`
    : w.vendor?.name ?? w.id;
  const amount = w.claim ?? w.invoice;
  const sla = fmtSlaRemaining(w.slaDueAt);
  const hasException = !!w.activeExceptionId;
  const cardBorder = hasException
    ? "border-amber-300 bg-amber-50/30"
    : sla?.warn
    ? "border-red-200"
    : "border-slate-200";

  return (
    <Link
      to={`/workflows/${w.id}`}
      className={`block bg-white border ${cardBorder} rounded-lg p-3 shadow-sm hover:border-blue-400 hover:shadow transition`}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="font-semibold text-sm text-slate-900 truncate">{w.id}</div>
        <span
          className={`text-[10px] uppercase tracking-wide font-medium px-1.5 py-0.5 rounded whitespace-nowrap ${STATUS_COLOR[w.status]}`}
        >
          {STATUS_LABEL[w.status]}
        </span>
      </div>
      <div className="text-xs text-slate-500 mt-0.5 truncate">{subtitle}</div>
      {amount && (
        <div className="text-xs text-slate-700 mt-1 flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-slate-900">
            {amount.currency} {amount.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
          {w.claim && (
            <span className="text-[10px] text-slate-500 capitalize">{w.claim.category}</span>
          )}
          {w.verdict && (
            <span className={`text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded font-medium ${VERDICT_COLOR[w.verdict]}`}>
              {w.verdict}
            </span>
          )}
        </div>
      )}
      <div className="mt-2 flex items-center justify-between gap-2">
        <div className="text-[10px] text-slate-500 truncate">{w.currentPhase}</div>
        {sla && (
          <div className={`text-[10px] flex items-center gap-1 whitespace-nowrap ${sla.warn ? "text-red-600 font-medium" : "text-slate-500"}`}>
            <Clock size={10} />
            {sla.text}
          </div>
        )}
      </div>
      <div className="h-1 bg-slate-100 rounded mt-1">
        <div className={`h-1 rounded ${PROGRESS_BAR[w.status]}`} style={{ width: `${pct}%` }} />
      </div>
      {hasException && (
        <div className="mt-2 flex items-center gap-1 text-[10px] text-amber-800 font-medium">
          <AlertTriangle size={11} />
          exception · awaiting reviewer
        </div>
      )}
    </Link>
  );
}

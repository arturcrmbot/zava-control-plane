// src/client/components/PhaseTimeline.tsx
import { PHASE_ORDER, EXPENSE_PHASE_ORDER, HIRING_PHASE_ORDER, type Phase, type PhaseName } from "@shared/types";

type WorkflowType = "invoice-p2p" | "expense-claim" | "hiring";

function phaseOrderFor(type: WorkflowType | undefined): PhaseName[] {
  if (type === "expense-claim") return EXPENSE_PHASE_ORDER;
  if (type === "hiring") return HIRING_PHASE_ORDER;
  return PHASE_ORDER;
}

type DisplayStatus = Phase["status"] | "not_started";

const STATUS_LABEL: Record<DisplayStatus, string> = {
  not_started: "pending",
  pending: "pending",
  in_progress: "in progress",
  completed: "completed",
  failed: "failed",
};

const STATUS_STYLE: Record<DisplayStatus, string> = {
  completed: "text-emerald-700",
  in_progress: "text-blue-700",
  failed: "text-red-700",
  pending: "text-slate-400",
  not_started: "text-slate-400",
};

export default function PhaseTimeline({ phases, workflowType }: { phases: Phase[]; workflowType?: WorkflowType }) {
  const byName = new Map(phases.map(p => [p.name, p]));
  const order = phaseOrderFor(workflowType);
  return (
    <div className="space-y-1.5">
      {order.map(name => {
        const p = byName.get(name);
        const status: DisplayStatus = p?.status ?? "not_started";
        const duration = p?.startedAt && p?.completedAt ? Math.round(p.completedAt - p.startedAt) : null;
        const tools = p?.toolCalls.length ?? 0;
        return (
          <div key={name} className="flex items-center gap-3 text-xs bg-white border border-slate-200 rounded px-3 py-2">
            <div className={`w-32 font-medium ${p ? "text-slate-800" : "text-slate-400"}`}>{name}</div>
            <div className={`text-[10px] uppercase tracking-wide font-medium ${STATUS_STYLE[status]}`}>{STATUS_LABEL[status]}</div>
            {duration != null && <div className="text-slate-500">{duration} ms</div>}
            <div className="ml-auto text-slate-500">{tools} tool{tools === 1 ? "" : "s"}</div>
          </div>
        );
      })}
    </div>
  );
}

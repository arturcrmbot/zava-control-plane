// src/client/components/PhaseTimeline.tsx
import { type Phase, type Workflow } from "@shared/types";
import { usePhaseOrderFor } from "@client/hooks/useDomainRegistry";

type DisplayStatus = Phase["status"] | "not_started";

const STATUS_LABEL: Record<DisplayStatus, string> = {
  not_started: "pending",
  pending: "pending",
  in_progress: "in progress",
  completed: "completed",
  failed: "failed",
};

const STATUS_STYLE: Record<DisplayStatus, string> = {
  completed: "text-emerald-700 dark:text-emerald-400",
  in_progress: "text-blue-700 dark:text-blue-300",
  failed: "text-red-700 dark:text-red-400",
  pending: "text-slate-400 dark:text-slate-500",
  not_started: "text-slate-400 dark:text-slate-500",
};

export default function PhaseTimeline({ phases, workflowType }: {
  phases: Phase[]; workflowType?: Workflow["type"];
}) {
  const phaseList = phases ?? [];
  const byName = new Map<string, Phase>(phaseList.map(p => [p.name, p]));
  const order = usePhaseOrderFor(workflowType);
  // Fallback: if the registry hasn't loaded yet (or this workflow_type
  // isn't in DOMAINS), render whatever phases the workflow itself
  // carries — never the wrong hardcoded list.
  const names = order.length > 0 ? order : phaseList.map(p => p.name);
  return (
    <div className="space-y-1.5">
      {names.map(name => {
        const p = byName.get(name);
        const status: DisplayStatus = p?.status ?? "not_started";
        const duration = p?.startedAt && p?.completedAt ? Math.round(p.completedAt - p.startedAt) : null;
        const tools = p?.toolCalls.length ?? 0;
        return (
          <div key={name} className="flex items-center gap-3 text-xs bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded px-3 py-2">
            <div className={`w-32 font-medium ${p ? "text-slate-800 dark:text-slate-100" : "text-slate-400 dark:text-slate-500"}`}>{name}</div>
            <div className={`text-[10px] uppercase tracking-wide font-medium ${STATUS_STYLE[status]}`}>{STATUS_LABEL[status]}</div>
            {duration != null && <div className="text-slate-500 dark:text-slate-400">{duration} ms</div>}
            <div className="ml-auto text-slate-500 dark:text-slate-400">{tools} tool{tools === 1 ? "" : "s"}</div>
          </div>
        );
      })}
    </div>
  );
}

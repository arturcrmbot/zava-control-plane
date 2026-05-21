import { type Phase, type Workflow } from "@shared/types";
import { Check, Loader2, Ban, CircleDashed } from "lucide-react";
import { usePhaseOrderFor } from "@client/hooks/useDomainRegistry";

type Status = "completed" | "in_progress" | "blocked" | "rejected" | "pending";

function classify(
  name: string, phases: Phase[], currentPhase: string,
  hasException: boolean, isRejected: boolean,
): Status {
  const p = phases.find(x => x.name === name);
  // A rejected workflow paints the rejection phase red and skips remaining
  // phases visually — even though `phase.completed:Arbitrate` fired before
  // the rejection event, we want the operator to see the workflow ended
  // here, not that everything went green.
  if (isRejected && name === currentPhase) return "rejected";
  if (p?.status === "completed") return "completed";
  if (name === currentPhase && hasException) return "blocked";
  if (name === currentPhase) return "in_progress";
  return "pending";
}

const Icon = ({ s }: { s: Status }) => {
  if (s === "completed") return <Check size={14} className="text-emerald-600" />;
  if (s === "in_progress") return <Loader2 size={14} className="text-blue-600 animate-spin" />;
  if (s === "blocked") return <Ban size={14} className="text-red-600" />;
  if (s === "rejected") return <Ban size={14} className="text-red-600" />;
  return <CircleDashed size={14} className="text-slate-400 dark:text-slate-500" />;
};

const PILL: Record<Status, string> = {
  completed: "bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-800 text-emerald-800",
  in_progress: "bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800 text-blue-800",
  blocked: "bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-800 text-red-800",
  rejected: "bg-red-50 dark:bg-red-950/30 border-red-300 text-red-800 ring-1 ring-red-200",
  pending: "bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400",
};

export default function PhaseRibbon({ workflow, phases }: {
  workflow: Workflow; phases: Phase[];
}) {
  const hasException = !!workflow.activeExceptionId;
  const isRejected = workflow.status === "failed";
  const orderFromRegistry = usePhaseOrderFor(workflow.type);
  const phaseList = phases ?? [];
  // Fallback to the workflow's own phase list if the registry hasn't
  // loaded yet — never render the wrong hardcoded order.
  const order = orderFromRegistry.length > 0 ? orderFromRegistry : phaseList.map(p => p.name);
  return (
    <div className="flex flex-wrap items-center gap-y-2 gap-x-1.5" data-testid="phase-ribbon">
      {order.map((name, i) => {
        const s = classify(name, phaseList, workflow.currentPhase, hasException, isRejected);
        return (
          <div key={name} className="flex items-center gap-1.5">
            <div className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 border ${PILL[s]}`}>
              <Icon s={s} />
              <span className="text-xs font-medium whitespace-nowrap">{name}</span>
            </div>
            {i < order.length - 1 &&
              <div className="h-px w-3 bg-slate-300" />}
          </div>
        );
      })}
    </div>
  );
}

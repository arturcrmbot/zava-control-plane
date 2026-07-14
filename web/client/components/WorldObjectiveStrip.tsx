import type { WorldObjective } from "@client/hooks/useWorldSimulation";

// One compact row summarising the newest objective's lifecycle state — no new
// page, chart or control. It sits beside the existing Durable causal strip so
// the objective/command kernel is observable in both world views.
const OBJECTIVE_STATUS_TONE: Record<string, string> = {
  open: "text-slate-600 dark:text-slate-300",
  claimed: "text-sky-700 dark:text-sky-400",
  acting: "text-amber-700 dark:text-amber-400",
  evaluating: "text-violet-700 dark:text-violet-400",
  resolved: "text-emerald-700 dark:text-emerald-400",
  failed: "text-rose-700 dark:text-rose-400",
  superseded: "text-slate-500 dark:text-slate-400",
};

export function WorldObjectiveStrip({
  testId,
  objectives,
}: {
  testId: string;
  objectives?: WorldObjective[];
}) {
  if (!objectives || objectives.length === 0) return null;
  const objective = objectives[objectives.length - 1];
  const tone = OBJECTIVE_STATUS_TONE[objective.status] ?? "text-slate-600 dark:text-slate-300";
  return (
    <section
      data-testid={testId}
      className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/40 px-3 py-2 text-xs"
    >
      <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        Objective
      </span>
      <span className="font-mono text-slate-700 dark:text-slate-200">{objective.type}</span>
      <span
        data-testid={`${testId}-status`}
        className={`font-semibold uppercase tracking-wide ${tone}`}
      >
        {objective.status}
      </span>
      <span className="text-slate-500 dark:text-slate-400">P{objective.priority}</span>
      <span className="font-mono text-[10px] text-slate-500 dark:text-slate-400">
        {objective.claimed_by ?? objective.owner_function}
      </span>
    </section>
  );
}

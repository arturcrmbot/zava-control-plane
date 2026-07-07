import { Check, Loader2, Circle } from "lucide-react";

export function PlanChecklist({ plan }: { plan: { title: string; status: string }[] }) {
  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-3">
      <p className="mb-2 text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Plan</p>
      <ul className="space-y-1.5">
        {plan.map((p, i) => (
          <li key={i} className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
            {p.status === "done" ? <Check size={14} className="text-emerald-500 dark:text-emerald-400" />
              : p.status === "in_progress" ? <Loader2 size={14} className="animate-spin text-blue-500 dark:text-blue-400" />
              : <Circle size={14} className="text-slate-400 dark:text-slate-600" />}
            {p.title}
          </li>
        ))}
      </ul>
    </div>
  );
}

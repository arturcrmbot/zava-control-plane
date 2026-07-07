import { Check, Loader2, Circle } from "lucide-react";

export function PlanChecklist({ plan }: { plan: { title: string; status: string }[] }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
      <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Plan</p>
      <ul className="space-y-1.5">
        {plan.map((p, i) => (
          <li key={i} className="flex items-center gap-2 text-sm text-slate-300">
            {p.status === "done" ? <Check size={14} className="text-emerald-400" />
              : p.status === "in_progress" ? <Loader2 size={14} className="animate-spin text-sky-400" />
              : <Circle size={14} className="text-slate-600" />}
            {p.title}
          </li>
        ))}
      </ul>
    </div>
  );
}

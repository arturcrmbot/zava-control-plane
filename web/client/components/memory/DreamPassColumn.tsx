import { Sparkles } from "lucide-react";
import { useDreamPassesRecent } from "@client/hooks/useMemoryQueries";

export default function DreamPassColumn() {
  const passes = useDreamPassesRecent(30);
  return (
    <section className="flex-1 min-w-0 bg-white border border-slate-200 rounded-lg p-3 dark:bg-slate-900 dark:border-slate-700">
      <header className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100 mb-2">
        <Sparkles size={16} /> Dream passes <span className="text-xs text-slate-400">({passes.length})</span>
      </header>
      <ol className="space-y-2 max-h-[70vh] overflow-y-auto">
        {passes.map((p) => (
          <li key={p.id} className="text-xs p-2 rounded border-l-2 border-purple-400 bg-slate-50 dark:bg-slate-800/40">
            <div className="text-[10px] uppercase tracking-wide text-slate-400">{p.id}</div>
            <div className="text-slate-700 dark:text-slate-200">
              <strong>{p.domain}</strong> · {p.status ?? "?"} · proposed {p.candidates_proposed ?? 0}, promoted {p.candidates_promoted ?? 0}
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">{p.started_at ?? "—"} → {p.completed_at ?? "—"}</div>
          </li>
        ))}
        {passes.length === 0 && <li className="text-xs text-slate-400">No runs yet — try the Trigger button.</li>}
      </ol>
    </section>
  );
}

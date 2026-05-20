import { BookOpen } from "lucide-react";
import { useActiveLessons } from "@client/hooks/useMemoryQueries";

export default function ActiveLessonsColumn({ domain }: { domain?: string }) {
  const lessons = useActiveLessons(domain);
  return (
    <section className="flex-1 min-w-0 bg-white border border-slate-200 rounded-lg p-3 dark:bg-slate-900 dark:border-slate-700">
      <header className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100 mb-2">
        <BookOpen size={16} /> Active lessons <span className="text-xs text-slate-400">({lessons.length})</span>
      </header>
      <ul className="grid grid-cols-1 gap-2 max-h-[70vh] overflow-y-auto">
        {lessons.map((l) => (
          <li key={l.id} className="text-xs p-2 rounded border border-slate-200 dark:border-slate-700">
            <div className="text-[10px] uppercase tracking-wide text-slate-400">
              {l.domain ?? "—"} · Δ {l.rubric_score_delta?.toFixed(2) ?? "—"} (n={l.experiment_n ?? "—"})
            </div>
            <div className="text-slate-700 dark:text-slate-200 leading-snug">{l.body}</div>
            <div className="text-[10px] text-slate-400 mt-1">
              promoted {l.promoted_at ?? "—"} · by {l.proposed_by ?? "—"}
            </div>
          </li>
        ))}
        {lessons.length === 0 && <li className="text-xs text-slate-400">No lessons promoted yet.</li>}
      </ul>
    </section>
  );
}

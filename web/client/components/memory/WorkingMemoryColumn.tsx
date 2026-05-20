import { Brain } from "lucide-react";
import { useWorkingNotes } from "@client/hooks/useMemoryQueries";

export default function WorkingMemoryColumn({ agentSkill }: { agentSkill?: string }) {
  const notes = useWorkingNotes(50, agentSkill);
  return (
    <section className="flex-1 min-w-0 bg-white border border-slate-200 rounded-lg p-3 dark:bg-slate-900 dark:border-slate-700">
      <header className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100 mb-2">
        <Brain size={16} /> Working memory <span className="text-xs text-slate-400">({notes.length})</span>
      </header>
      <ul className="space-y-2 max-h-[70vh] overflow-y-auto">
        {notes.map((n) => (
          <li key={n.id} className="text-xs border-l-2 border-blue-400 pl-2">
            <div className="text-[10px] uppercase tracking-wide text-slate-400">
              {n.agent_skill ?? "—"} · {n.kind ?? "—"} · {n.workflow_id ?? "—"}
            </div>
            <div className="text-slate-700 dark:text-slate-200">{n.body ?? <em>(empty)</em>}</div>
            <div className="text-[10px] text-slate-400 mt-0.5">
              {n.captured_at ?? "—"}{n.consumed_by_dream_pass ? " · consumed" : ""}
            </div>
          </li>
        ))}
        {notes.length === 0 && <li className="text-xs text-slate-400">No working notes yet.</li>}
      </ul>
    </section>
  );
}

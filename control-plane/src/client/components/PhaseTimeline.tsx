// src/client/components/PhaseTimeline.tsx
import type { Phase } from "@shared/types";

export default function PhaseTimeline({ phases }: { phases: Phase[] }) {
  return (
    <div className="space-y-1">
      {phases.map(p => (
        <div key={p.name} className="flex items-center gap-3 text-xs border border-slate-800 rounded px-2 py-1.5 bg-slate-900/30">
          <div className="w-32 text-slate-200">{p.name}</div>
          <div className={`text-[10px] uppercase ${p.status === "completed" ? "text-emerald-400" : p.status === "in_progress" ? "text-blue-400" : "text-slate-500"}`}>{p.status}</div>
          {p.startedAt && p.completedAt && <div className="text-slate-500">{p.completedAt - p.startedAt} ms</div>}
          <div className="ml-auto text-slate-500">{p.toolCalls.length} tools</div>
        </div>
      ))}
    </div>
  );
}

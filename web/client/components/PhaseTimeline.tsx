// src/client/components/PhaseTimeline.tsx
import type { Phase } from "@shared/types";

export default function PhaseTimeline({ phases }: { phases: Phase[] }) {
  return (
    <div className="space-y-1.5">
      {phases.map(p => (
        <div key={p.name} className="flex items-center gap-3 text-xs bg-white border border-slate-200 rounded px-3 py-2">
          <div className="w-32 text-slate-800 font-medium">{p.name}</div>
          <div className={`text-[10px] uppercase tracking-wide font-medium ${p.status === "completed" ? "text-emerald-700" : p.status === "in_progress" ? "text-blue-700" : "text-slate-400"}`}>{p.status}</div>
          {p.startedAt && p.completedAt && <div className="text-slate-500">{Math.round(p.completedAt - p.startedAt)} ms</div>}
          <div className="ml-auto text-slate-500">{p.toolCalls.length} tools</div>
        </div>
      ))}
    </div>
  );
}

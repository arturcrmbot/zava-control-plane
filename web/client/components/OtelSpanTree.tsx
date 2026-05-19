// src/client/components/OtelSpanTree.tsx
import type { OtelSpan } from "@shared/types";

export default function OtelSpanTree({ spans }: { spans: OtelSpan[] }) {
  const sorted = [...spans].sort((a, b) => a.startMs - b.startMs);
  return (
    <div className="space-y-1.5 font-mono text-xs">
      {sorted.map(s => (
        <div key={s.spanId} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded px-3 py-2">
          <div className="flex justify-between">
            <span className="text-slate-800 dark:text-slate-100 font-medium">{s.name}</span>
            <span className="text-slate-500 dark:text-slate-400">{Math.round(s.endMs - s.startMs)} ms</span>
          </div>
          <div className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">
            phase={s.attributes["workflow.phase"]}{s.attributes["tool.name"] ? ` · tool=${s.attributes["tool.name"]}` : ""}
            {s.attributes["llm.model"] ? ` · model=${s.attributes["llm.model"]}` : ""}
            {s.attributes["cost.usd"] != null ? ` · $${(s.attributes["cost.usd"] as number).toFixed(4)}` : ""}
          </div>
        </div>
      ))}
    </div>
  );
}

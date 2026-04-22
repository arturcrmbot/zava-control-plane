// src/client/components/OtelSpanTree.tsx
import type { OtelSpan } from "@shared/types";

export default function OtelSpanTree({ spans }: { spans: OtelSpan[] }) {
  const sorted = [...spans].sort((a, b) => a.startMs - b.startMs);
  return (
    <div className="space-y-1 font-mono text-xs">
      {sorted.map(s => (
        <div key={s.spanId} className="border border-slate-800 rounded px-2 py-1.5 bg-slate-900/30">
          <div className="flex justify-between">
            <span className="text-slate-200">{s.name}</span>
            <span className="text-slate-500">{s.endMs - s.startMs} ms</span>
          </div>
          <div className="text-[10px] text-slate-500">
            phase={s.attributes["workflow.phase"]}{s.attributes["tool.name"] ? ` tool=${s.attributes["tool.name"]}` : ""}
            {s.attributes["llm.model"] ? ` model=${s.attributes["llm.model"]}` : ""}
            {s.attributes["cost.usd"] != null ? ` $=${(s.attributes["cost.usd"] as number).toFixed(4)}` : ""}
          </div>
        </div>
      ))}
    </div>
  );
}

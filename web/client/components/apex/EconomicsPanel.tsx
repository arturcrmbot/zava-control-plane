// web/client/components/apex/EconomicsPanel.tsx
import type { Economics } from "@shared/types";

export default function EconomicsPanel({ e }: { e: Economics }) {
  const tiles = [
    { k: "Compute cost", v: `$${e.computeCostUsd.toFixed(2)}` },
    { k: "Model calls",  v: String(e.modelCalls) },
    { k: "Tool calls",   v: String(e.toolCalls) },
    { k: "Days elapsed", v: String(e.daysElapsed.toFixed(1)) },
    { k: "SLA token",    v: e.slaToken },
  ];
  return (
    <div className="panel" data-testid="economics-panel">
      <div className="panel-header">Economics</div>
      <div className="panel-body grid grid-cols-2 gap-2">
        {tiles.map(t => (
          <div key={t.k} className="border border-slate-200 rounded p-2">
            <div className="text-[10px] uppercase tracking-wide text-slate-500">{t.k}</div>
            <div className="text-sm font-semibold text-slate-900">{t.v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

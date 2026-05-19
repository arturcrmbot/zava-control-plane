// web/client/components/apex/EconomicsPanel.tsx
import type { Economics } from "@shared/types";

function _fmtTokens(n: number | undefined): string {
  if (!n) return "0";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "k";
  return String(n);
}

export default function EconomicsPanel({ e }: { e: Economics }) {
  const cost = (e.modelCostUsd ?? e.computeCostUsd ?? 0).toFixed(4);
  const tiles = [
    { k: "Model cost",    v: `$${cost}` },
    { k: "Input tokens",  v: _fmtTokens(e.inputTokens) },
    { k: "Output tokens", v: _fmtTokens(e.outputTokens) },
    { k: "Model calls",   v: String(e.modelCalls) },
    { k: "Tool calls",    v: String(e.toolCalls) },
    { k: "Days elapsed",  v: String(e.daysElapsed.toFixed(1)) },
    { k: "SLA token",     v: e.slaToken },
  ];
  return (
    <div className="panel" data-testid="economics-panel">
      <div className="panel-header">Economics</div>
      <div className="panel-body space-y-2">
        {tiles.map(t => (
          <div key={t.k} className="border border-slate-200 dark:border-slate-700 rounded px-2 py-1.5">
            <div className="text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400 leading-tight">{t.k}</div>
            <div className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate">{t.v}</div>
          </div>
        ))}
        {e.pricingSource && (
          <div className="text-[10px] text-slate-400 dark:text-slate-500 pt-1" title="Source of per-million-token rates">
            pricing: {e.pricingSource}
          </div>
        )}
      </div>
    </div>
  );
}

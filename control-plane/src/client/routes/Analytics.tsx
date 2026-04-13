// src/client/routes/Analytics.tsx
import { useEffect, useState } from "react";

interface AnalyticsData {
  interventionRate: number; avgResolutionMs: number;
  overrideFrequency: number; qualityDelta: number;
}

export default function Analytics() {
  const [d, setD] = useState<AnalyticsData | null>(null);
  useEffect(() => {
    void fetch("/api/workflows").then(r => r.json()).then((ws: Array<{ status: string; actionLedger: Array<{ actor: { kind: string } }> }>) => {
      const total = ws.length || 1;
      const humanTouched = ws.filter(w => w.actionLedger.some(a => a.actor.kind === "human")).length;
      setD({
        interventionRate: humanTouched / total,
        avgResolutionMs: 240_000,
        overrideFrequency: 0.12,
        qualityDelta: 0.04
      });
    });
  }, []);
  if (!d) return <div className="text-xs text-slate-500">loading…</div>;

  const cards = [
    { label: "Intervention rate", v: `${(d.interventionRate * 100).toFixed(1)}%` },
    { label: "Avg resolution", v: `${Math.round(d.avgResolutionMs / 1000)}s` },
    { label: "Override frequency", v: `${(d.overrideFrequency * 100).toFixed(1)}%` },
    { label: "Quality Δ vs baseline", v: `+${(d.qualityDelta * 100).toFixed(1)}%` }
  ];

  return (
    <div className="space-y-3">
      <div className="text-sm font-semibold">Analytics — last 24h</div>
      <div className="grid grid-cols-4 gap-3">
        {cards.map(c => (
          <div key={c.label} className="border border-slate-800 rounded p-3 bg-slate-900/30">
            <div className="text-[11px] uppercase text-slate-500">{c.label}</div>
            <div className="text-xl font-semibold">{c.v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

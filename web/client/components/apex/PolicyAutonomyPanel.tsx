// web/client/components/apex/PolicyAutonomyPanel.tsx
import { useEffect, useState } from "react";

type Policy = { id: string; description: string; currentValue: number | string | boolean };

export default function PolicyAutonomyPanel() {
  const [items, setItems] = useState<Policy[]>([]);
  useEffect(() => { void fetch("/api/policy/").then(r => r.json()).then(setItems); }, []);
  return (
    <div className="panel" data-testid="policy-autonomy">
      <div className="panel-header">Policy &amp; Autonomy</div>
      <div className="panel-body space-y-2">
        {items.length === 0 && <div className="text-xs text-slate-500">no policies loaded</div>}
        {items.map(p => {
          const v = typeof p.currentValue === "number" ? p.currentValue :
                    typeof p.currentValue === "boolean" ? (p.currentValue ? 1 : 0) : 0.5;
          const pct = Math.max(0, Math.min(1, v <= 1 ? v : v / 100));
          return (
            <div key={p.id}>
              <div className="flex justify-between text-xs">
                <span className="text-slate-700">{p.description}</span>
                <span className="text-slate-500">{String(p.currentValue)}</span>
              </div>
              <div className="h-1.5 bg-slate-200 rounded mt-1">
                <div className="h-1.5 bg-blue-500 rounded" style={{ width: `${pct * 100}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// web/client/components/apex/FleetEconomicsPanel.tsx
import { useEffect, useState } from "react";
import type { FleetEconomics } from "@shared/types";

export default function FleetEconomicsPanel() {
  const [d, setD] = useState<FleetEconomics | null>(null);
  useEffect(() => {
    const load = () => fetch("/api/fleet/economics").then(r => r.json()).then(setD);
    void load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);
  if (!d) return <div className="panel panel-body text-xs text-slate-500">loading economics…</div>;
  return (
    <div className="panel" data-testid="fleet-economics">
      <div className="panel-header">Fleet Economics</div>
      <div className="panel-body space-y-2 text-sm">
        <div>
          <div className="text-[10px] uppercase text-slate-500 leading-tight">Compute · session</div>
          <div className="font-semibold">${d.totalComputeCostUsd.toFixed(4)}</div>
        </div>
        <div>
          <div className="text-[10px] uppercase text-slate-500 leading-tight">Avg / workflow</div>
          <div className="font-semibold">${d.averageCostPerWorkflow.toFixed(4)}</div>
        </div>
        <div>
          <div className="text-[10px] uppercase text-slate-500 leading-tight">Model calls</div>
          <div className="font-semibold">{d.totalModelCalls}</div>
        </div>
        <div>
          <div className="text-[10px] uppercase text-slate-500 leading-tight">Tool calls</div>
          <div className="font-semibold">{d.totalToolCalls}</div>
        </div>
      </div>
    </div>
  );
}

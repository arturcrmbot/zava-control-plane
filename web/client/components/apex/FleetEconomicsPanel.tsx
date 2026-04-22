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
      <div className="panel-body grid grid-cols-2 gap-2 text-sm">
        <div><div className="text-[10px] uppercase text-slate-500">Compute (active)</div>
             <div className="font-semibold">${d.totalComputeCostUsd.toFixed(2)}</div></div>
        <div><div className="text-[10px] uppercase text-slate-500">Avg per wf</div>
             <div className="font-semibold">${d.averageCostPerWorkflow.toFixed(2)}</div></div>
        <div><div className="text-[10px] uppercase text-slate-500">Model calls</div>
             <div className="font-semibold">{d.totalModelCalls}</div></div>
        <div><div className="text-[10px] uppercase text-slate-500">Tool calls</div>
             <div className="font-semibold">{d.totalToolCalls}</div></div>
      </div>
    </div>
  );
}

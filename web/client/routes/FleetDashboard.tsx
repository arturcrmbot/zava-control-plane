// src/client/routes/FleetDashboard.tsx
import { useMemo, useState } from "react";
import { useWorkflows } from "../hooks/useWorkflows";
import { useExceptions } from "../hooks/useExceptions";
import WorkflowCard from "../components/WorkflowCard";
import DevPanel from "../components/DevPanel";
import KpiTileRow from "../components/apex/KpiTileRow";
import ExceptionCardCompact from "../components/apex/ExceptionCardCompact";
import FleetEconomicsPanel from "../components/apex/FleetEconomicsPanel";
import PolicyAutonomyPanel from "../components/apex/PolicyAutonomyPanel";

// One filter chip per "demo arc" the operator might be telling. Keep
// minimal — most operators want everything; the chip exists for the
// POC3 storyboard beat ("show me only creative campaigns"). The selector
// applies a single workflow_type prefix; "all" disables it.
const CHIPS: Array<{ key: string; label: string; types: string[] }> = [
  { key: "all", label: "All domains", types: [] },
  { key: "creative-campaign", label: "Creative Campaigns", types: ["creative-campaign"] },
  { key: "finance", label: "Finance", types: ["expense-claim", "ap-invoice", "purchase-order", "treasury-fx", "contract-renewal"] },
  { key: "hiring", label: "Hiring", types: ["hiring"] },
  { key: "fleet", label: "Fleet ops", types: ["travel-preapproval", "vendor-kyc", "employee-onboarding", "it-access-request", "perf-review", "contract-review", "privacy-dpia"] },
];

export default function FleetDashboard() {
  const allWorkflows = useWorkflows();
  const { items: exceptions } = useExceptions();
  const topExceptions = exceptions.slice(0, 3);
  const [chip, setChip] = useState<string>("all");

  const workflows = useMemo(() => {
    const cfg = CHIPS.find(c => c.key === chip);
    if (!cfg || cfg.types.length === 0) return allWorkflows;
    return allWorkflows.filter(w => cfg.types.includes(w.type));
  }, [allWorkflows, chip]);

  return (
    <div className="grid grid-cols-4 gap-4 min-w-0">
      <div className="col-span-3 space-y-4 min-w-0">
        <div className="flex items-center gap-3">
          <div>
            <div className="text-xl font-semibold text-slate-900">Control Plane Overview</div>
            <div className="text-xs text-slate-500">
              Operational status across all domains
            </div>
          </div>
          <div className="ml-auto"><DevPanel /></div>
        </div>
        <KpiTileRow workflows={allWorkflows} exceptionsCount={exceptions.length} />
        <div className="panel">
          <div className="panel-header">Exceptions Requiring Attention</div>
          <div className="panel-body grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {topExceptions.length === 0 &&
              <div className="text-xs text-slate-500 col-span-full italic">No open exceptions.</div>}
            {topExceptions.map(e => <ExceptionCardCompact key={e.id} e={e} />)}
          </div>
        </div>
        <div className="panel">
          <div className="panel-header flex items-center justify-between gap-3 flex-wrap">
            <span>Active Workflows</span>
            <div className="flex items-center gap-1 ml-auto" data-testid="fleet-domain-chips">
              {CHIPS.map(c => {
                const active = chip === c.key;
                return (
                  <button
                    key={c.key}
                    onClick={() => setChip(c.key)}
                    data-testid={`fleet-chip-${c.key}`}
                    className={`text-[11px] px-2 py-1 rounded font-medium transition-colors whitespace-nowrap ${
                      active
                        ? c.key === "creative-campaign"
                          ? "bg-fuchsia-600 text-white"
                          : "bg-slate-700 text-white"
                        : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                  >
                    {c.label}
                  </button>
                );
              })}
            </div>
            <span className="text-[11px] text-slate-500 whitespace-nowrap">{workflows.length} shown</span>
          </div>
          <div className="panel-body grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-3">
            {workflows.length === 0 && (
              <div className="text-xs text-slate-500 italic col-span-full">No active workflows in this filter.</div>
            )}
            {workflows.map(w => <WorkflowCard key={w.id} w={w} />)}
          </div>
        </div>
      </div>

      <div className="col-span-1 space-y-3">
        <FleetEconomicsPanel />
        <PolicyAutonomyPanel />
      </div>
    </div>
  );
}

// src/client/routes/FleetDashboard.tsx
import { useWorkflows } from "../hooks/useWorkflows";
import { useExceptions } from "../hooks/useExceptions";
import WorkflowCard from "../components/WorkflowCard";
import DevPanel from "../components/DevPanel";
import KpiTileRow from "../components/apex/KpiTileRow";
import ExceptionCardCompact from "../components/apex/ExceptionCardCompact";
import FleetEconomicsPanel from "../components/apex/FleetEconomicsPanel";
import PolicyAutonomyPanel from "../components/apex/PolicyAutonomyPanel";

export default function FleetDashboard() {
  const workflows = useWorkflows();
  const { items: exceptions } = useExceptions();
  const topExceptions = exceptions.slice(0, 3);

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
        <KpiTileRow workflows={workflows} exceptionsCount={exceptions.length} />
        <div className="panel">
          <div className="panel-header">Exceptions Requiring Attention</div>
          <div className="panel-body grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {topExceptions.length === 0 &&
              <div className="text-xs text-slate-500 col-span-full italic">No open exceptions.</div>}
            {topExceptions.map(e => <ExceptionCardCompact key={e.id} e={e} />)}
          </div>
        </div>
        <div className="panel">
          <div className="panel-header flex items-center justify-between">
            <span>Active Workflows</span>
            <span className="text-[11px] text-slate-500">{workflows.length} shown</span>
          </div>
          <div className="panel-body grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-3">
            {workflows.length === 0 && (
              <div className="text-xs text-slate-500 italic col-span-full">No active workflows.</div>
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

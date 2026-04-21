// src/client/routes/FleetDashboard.tsx
import { useMemo, useState } from "react";
import { useWorkflows } from "../hooks/useWorkflows";
import WorkflowCard from "../components/WorkflowCard";
import DevPanel from "../components/DevPanel";

export default function FleetDashboard() {
  const workflows = useWorkflows();
  const [phaseFilter, setPhaseFilter] = useState<string>("");
  const [agencyFilter, setAgencyFilter] = useState<string>("");
  const [exceptionsOnly, setExceptionsOnly] = useState(false);

  const filtered = useMemo(() =>
    workflows.filter(w =>
      (!phaseFilter || w.currentPhase === phaseFilter) &&
      (!agencyFilter || w.agency === agencyFilter) &&
      (!exceptionsOnly || !!w.activeExceptionId)
    ), [workflows, phaseFilter, agencyFilter, exceptionsOnly]);

  const counts = {
    total: workflows.length,
    inFlight: workflows.filter(w => w.status === "in_progress").length,
    awaiting: workflows.filter(w => w.status === "awaiting_hitl").length,
    completed: workflows.filter(w => w.status === "completed").length,
    exceptions: workflows.filter(w => w.activeExceptionId).length
  };
  const agencies = Array.from(new Set(workflows.map(w => w.agency))).sort();

  return (
    <div className="space-y-4">
      <DevPanel />
      <div className="grid grid-cols-5 gap-3">
        {Object.entries(counts).map(([k, v]) => (
          <div key={k} className="border border-slate-800 rounded p-3 bg-slate-900/50">
            <div className="text-[11px] text-slate-500 uppercase">{k.replace(/([A-Z])/g, " $1")}</div>
            <div className="text-xl font-semibold">{v}</div>
          </div>
        ))}
      </div>
      <div className="flex gap-2 text-sm items-center">
        <select value={phaseFilter} onChange={e => setPhaseFilter(e.target.value)}
          className="bg-slate-900 border border-slate-800 rounded px-2 py-1 text-xs">
          <option value="">All phases</option>
          {["Intake", "Validation", "Routing", "Approval", "Payment", "Reconciliation"].map(p => <option key={p}>{p}</option>)}
        </select>
        <select value={agencyFilter} onChange={e => setAgencyFilter(e.target.value)}
          className="bg-slate-900 border border-slate-800 rounded px-2 py-1 text-xs">
          <option value="">All agencies</option>
          {agencies.map(a => <option key={a}>{a}</option>)}
        </select>
        <label className="text-xs text-slate-300 flex items-center gap-1">
          <input type="checkbox" checked={exceptionsOnly} onChange={e => setExceptionsOnly(e.target.checked)} />
          Exceptions only
        </label>
        <div className="ml-auto text-xs text-slate-500">{filtered.length} shown</div>
      </div>
      <div className="grid grid-cols-4 gap-2">
        {filtered.map(w => <WorkflowCard key={w.id} w={w} />)}
      </div>
    </div>
  );
}

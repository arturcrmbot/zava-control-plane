// src/client/components/WhatIfPanel.tsx
import { useState } from "react";

export default function WhatIfPanel({ policyId }: { policyId: string }) {
  const [value, setValue] = useState<string>("");
  const [result, setResult] = useState<{ wouldBeDifferent: number; totalEvaluated: number; impactedWorkflowIds: string[] } | null>(null);

  const run = async () => {
    const r = await fetch("/api/policy/dry-run", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ policyId, proposedValue: Number(value), scopeDays: 7 })
    });
    setResult(await r.json());
  };

  const propose = async () => {
    await fetch("/api/policy/propose-change", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ policyId, proposedValue: Number(value), rationale: "Dry-run accepted", proposedBy: "finance-controller@zava" })
    });
    alert("Change proposed. A PR has been opened for governance review.");
  };

  return (
    <div className="panel panel-body space-y-3">
      <div className="text-[11px] uppercase tracking-wide text-slate-500">What-if analysis</div>
      <div className="flex gap-2 items-center">
        <input value={value} onChange={e => setValue(e.target.value)} placeholder="proposed value"
          className="bg-white border border-slate-300 rounded px-2 py-1 text-xs w-40 focus:outline-none focus:ring-2 focus:ring-blue-300" />
        <button onClick={run} className="btn-secondary text-xs py-1">Run dry-run</button>
      </div>
      {result && (
        <div className="text-xs text-slate-700 space-y-1">
          <div>Scope: last 7 days. Evaluated {result.totalEvaluated} workflows.</div>
          <div className="text-emerald-700 font-medium">
            {result.wouldBeDifferent} would have decided differently.
          </div>
          {result.impactedWorkflowIds.length > 0 && (
            <div className="text-slate-500">Impacted: {result.impactedWorkflowIds.join(", ")}</div>
          )}
          <button onClick={propose} className="btn-primary text-xs mt-2 py-1">
            Propose as change (opens PR)
          </button>
        </div>
      )}
    </div>
  );
}

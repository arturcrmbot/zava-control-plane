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
      body: JSON.stringify({ policyId, proposedValue: Number(value), rationale: "Dry-run accepted", proposedBy: "finance-controller@wpp" })
    });
    alert("Change proposed. A PR has been opened for governance review.");
  };

  return (
    <div className="border border-slate-800 rounded p-3 bg-slate-900/30 space-y-2">
      <div className="text-xs uppercase text-slate-500">What-if analysis</div>
      <div className="flex gap-2 items-center">
        <input value={value} onChange={e => setValue(e.target.value)} placeholder="proposed value"
          className="bg-slate-950 border border-slate-800 rounded px-2 py-1 text-xs w-40" />
        <button onClick={run} className="text-xs px-3 py-1.5 border border-slate-700 rounded hover:bg-slate-800">Run dry-run</button>
      </div>
      {result && (
        <div className="text-xs text-slate-300 space-y-1">
          <div>Scope: last 7 days. Evaluated {result.totalEvaluated} workflows.</div>
          <div className="text-emerald-300">
            {result.wouldBeDifferent} would have decided differently.
          </div>
          {result.impactedWorkflowIds.length > 0 && (
            <div className="text-slate-400">Impacted: {result.impactedWorkflowIds.join(", ")}</div>
          )}
          <button onClick={propose} className="mt-2 text-xs px-3 py-1.5 bg-blue-600 rounded hover:bg-blue-500">
            Propose as change (opens PR)
          </button>
        </div>
      )}
    </div>
  );
}

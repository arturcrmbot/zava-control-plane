// src/client/routes/PolicyAndAutonomy.tsx
import { useEffect, useState } from "react";
import type { AutonomyPolicy } from "@shared/types";
import WhatIfPanel from "../components/WhatIfPanel";

export default function PolicyAndAutonomy() {
  const [policies, setPolicies] = useState<AutonomyPolicy[]>([]);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    void fetch("/api/policy").then(r => r.json()).then((ps: AutonomyPolicy[]) => {
      setPolicies(ps);
      if (ps[0]) setSelected(ps[0].id);
    });
  }, []);

  return (
    <div className="space-y-4">
      <div>
        <div className="text-lg font-semibold text-slate-900 dark:text-slate-100">Policy &amp; Autonomy</div>
        <div className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-3xl">
          Autonomy policy is declarative and version-controlled. This screen is <em>read-first</em>.
          Proposals go through a change-request flow — the Control Plane never mutates live governance.
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          {policies.map(p => (
            <button key={p.id}
              onClick={() => setSelected(p.id)}
              className={`w-full text-left panel panel-body transition ${selected === p.id ? "ring-2 ring-blue-500" : "hover:border-slate-300"}`}>
              <div className="text-sm font-medium text-slate-800 dark:text-slate-100">{p.id}</div>
              <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{p.description}</div>
              <div className="text-xs mt-2 text-slate-600 dark:text-slate-300">current: <span className="text-slate-900 dark:text-slate-100 font-medium">{String(p.currentValue)}</span></div>
              <div className="text-[10px] text-slate-400 dark:text-slate-500 mt-1">
                sha:{p.gitSha} · {p.author} · {new Date(p.updatedAt * 1000).toISOString().slice(0, 10)}
              </div>
            </button>
          ))}
        </div>
        <div>{selected && <WhatIfPanel policyId={selected} />}</div>
      </div>
    </div>
  );
}

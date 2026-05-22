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
    });
  }, []);

  return (
    <div className="space-y-4">
      <div className="text-lg font-semibold text-slate-900 dark:text-slate-100">Policy &amp; Autonomy</div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          {policies.map(p => (
            <button key={p.id}
              onClick={() => setSelected(selected === p.id ? null : p.id)}
              className={`w-full text-left panel panel-body transition ${selected === p.id ? "ring-2 ring-blue-500" : "hover:border-slate-300"}`}>
              <div className="text-sm font-medium text-slate-800 dark:text-slate-100">{p.id}</div>
              <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 line-clamp-2">{p.description}</div>
              <div className="text-xs mt-2 text-slate-600 dark:text-slate-300">
                current: <span className="text-slate-900 dark:text-slate-100 font-medium">{String(p.currentValue)}</span>
                <span className="text-[10px] text-slate-400 dark:text-slate-500 ml-2">
                  · sha:{p.gitSha.slice(0, 7)} · {new Date(p.updatedAt * 1000).toISOString().slice(0, 10)}
                </span>
              </div>
            </button>
          ))}
        </div>
        <div>
          {selected ? (
            <WhatIfPanel policyId={selected} />
          ) : (
            <div className="text-xs text-slate-400 dark:text-slate-500 italic px-2 py-6 text-center">
              Select a policy to run a what-if dry-run.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

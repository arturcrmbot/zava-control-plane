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
    <div className="space-y-3">
      <div className="text-sm font-semibold">Policy & Autonomy</div>
      <div className="text-xs text-slate-400">
        Current autonomy policy is declarative and version-controlled. This screen is <em>read-first</em>.
        Proposals go through a change-request flow — the Control Plane never mutates live governance.
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          {policies.map(p => (
            <button key={p.id}
              onClick={() => setSelected(p.id)}
              className={`w-full text-left border rounded p-3 bg-slate-900/30 ${selected === p.id ? "border-blue-500" : "border-slate-800"}`}>
              <div className="text-sm font-medium">{p.id}</div>
              <div className="text-xs text-slate-400">{p.description}</div>
              <div className="text-xs mt-2">current: <span className="text-slate-100">{String(p.currentValue)}</span></div>
              <div className="text-[10px] text-slate-500 mt-1">
                sha:{p.gitSha} · {p.author} · {new Date(p.updatedAt).toISOString().slice(0, 10)}
              </div>
            </button>
          ))}
        </div>
        <div>{selected && <WhatIfPanel policyId={selected} />}</div>
      </div>
    </div>
  );
}

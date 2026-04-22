// src/client/routes/Evaluations.tsx
import { useEffect, useState } from "react";

interface Eval {
  id: string; workflowId: string; ranAt: number;
  taskAdherence: number; safety: number; toolAccuracy: number;
}

export default function Evaluations() {
  const [items, setItems] = useState<Eval[]>([]);
  useEffect(() => {
    const tick = () => void fetch("/api/evals").then(r => r.json()).then(setItems);
    tick(); const i = setInterval(tick, 5000); return () => clearInterval(i);
  }, []);
  const avg = (k: keyof Eval) => items.length === 0 ? 0 : items.reduce((a, b) => a + (b[k] as number), 0) / items.length;

  return (
    <div className="space-y-3">
      <div className="text-sm font-semibold">Continuous Evaluation</div>
      <div className="text-xs text-slate-400">{items.length} evals on sampled traces.</div>
      <div className="grid grid-cols-3 gap-3">
        <Metric label="Task adherence" v={avg("taskAdherence")} />
        <Metric label="Safety" v={avg("safety")} />
        <Metric label="Tool accuracy" v={avg("toolAccuracy")} />
      </div>
      <div className="space-y-1 text-xs">
        {items.slice(0, 20).map(e => (
          <div key={e.id} className="border border-slate-800 rounded p-2 bg-slate-900/30">
            <a href={`/workflows/${e.workflowId}`} className="text-blue-300">{e.workflowId}</a>
            <span className="text-slate-500 ml-2">{new Date(e.ranAt).toLocaleTimeString()}</span>
            <span className="ml-4 text-slate-400">
              adh={e.taskAdherence.toFixed(2)} safe={e.safety.toFixed(2)} tool={e.toolAccuracy.toFixed(2)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Metric({ label, v }: { label: string; v: number }) {
  return (
    <div className="border border-slate-800 rounded p-3 bg-slate-900/30">
      <div className="text-[11px] uppercase text-slate-500">{label}</div>
      <div className="text-xl font-semibold">{(v * 100).toFixed(1)}%</div>
    </div>
  );
}

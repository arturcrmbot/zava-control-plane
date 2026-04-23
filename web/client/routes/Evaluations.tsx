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
    <div className="space-y-4">
      <div>
        <div className="text-lg font-semibold text-slate-900">Continuous Evaluation</div>
        <div className="text-xs text-slate-500 mt-0.5">{items.length} evals on sampled traces</div>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <Metric label="Task adherence" v={avg("taskAdherence")} />
        <Metric label="Safety" v={avg("safety")} />
        <Metric label="Tool accuracy" v={avg("toolAccuracy")} />
      </div>
      <div className="panel">
        <div className="panel-header">Recent runs</div>
        <div className="divide-y divide-slate-200">
          {items.length === 0 && (
            <div className="p-3 text-xs text-slate-500 italic">No evaluation runs yet.</div>
          )}
          {items.slice(0, 20).map(e => (
            <div key={e.id} className="flex items-center gap-3 px-3 py-2 text-xs">
              <a href={`/workflows/${e.workflowId}`} className="text-blue-700 hover:underline font-mono">{e.workflowId}</a>
              <span className="text-slate-400">{new Date(e.ranAt).toLocaleTimeString()}</span>
              <span className="ml-auto text-slate-600 font-mono">
                adh={e.taskAdherence.toFixed(2)} · safe={e.safety.toFixed(2)} · tool={e.toolAccuracy.toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Metric({ label, v }: { label: string; v: number }) {
  return (
    <div className="panel panel-body">
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-2xl font-semibold text-slate-900 mt-1">{(v * 100).toFixed(1)}%</div>
    </div>
  );
}

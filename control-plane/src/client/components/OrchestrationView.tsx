// src/client/components/OrchestrationView.tsx
import { useEffect, useState } from "react";

interface HistoryEntry {
  kind: string;
  payload: {
    name?: string;
    type?: string;
    stage?: string;
    step?: string;
    duration_ms?: number;
    reason?: string;
    error?: string;
    [k: string]: unknown;
  };
  at: number;
}

interface OrchestrationData {
  instance_id: string | null;
  status: string;
  history: HistoryEntry[];
}

const stepNames = ["Intake", "Validation", "Routing", "Approval", "Payment", "Reconciliation"] as const;

const exTypeLabel = (t: string | undefined) => {
  if (t === "agent") return <span className="text-purple-300 font-mono text-[10px]">[agt]</span>;
  if (t === "validator") return <span className="text-amber-300 font-mono text-[10px]">[val]</span>;
  if (t === "deterministic") return <span className="text-slate-400 font-mono text-[10px]">[det]</span>;
  return <span className="text-slate-500 font-mono text-[10px]">[ ?]</span>;
};

interface StepView {
  name: typeof stepNames[number];
  started?: HistoryEntry;
  completed?: HistoryEntry;
  failed?: HistoryEntry;
  suspended?: HistoryEntry;
  resumed?: HistoryEntry;
  rejected?: HistoryEntry;
  executors: HistoryEntry[];
  blocked?: HistoryEntry;
}

function deriveStepView(history: HistoryEntry[], name: string): StepView {
  const stepStart = history.find(h => h.kind === "step.started" && h.payload.step === name);
  const stepEnd = history.find(h => h.kind === "step.completed" && h.payload.step === name);
  const stepFailed = history.find(h => h.kind === "step.failed" && h.payload.step === name);
  const stepStartIdx = stepStart ? history.indexOf(stepStart) : -1;
  const stepEndIdx = stepEnd ? history.indexOf(stepEnd) : (stepFailed ? history.indexOf(stepFailed) : history.length);

  // Suspended/resumed events are siblings of the Approval step (no step name in payload — use ordering)
  const inWindow = (_h: HistoryEntry, idx: number) => idx > stepStartIdx && idx <= stepEndIdx;
  let suspended: HistoryEntry | undefined;
  let resumed: HistoryEntry | undefined;
  let blocked: HistoryEntry | undefined;
  let rejected: HistoryEntry | undefined;
  const executors: HistoryEntry[] = [];
  history.forEach((h, idx) => {
    if (!stepStart || !inWindow(h, idx)) return;
    if (h.kind === "executor.invoked" && h.payload.stage === "complete") executors.push(h);
    if (h.kind === "validator.blocked") blocked = h;
    if (h.kind === "suspended" && name === "Approval") suspended = h;
    if (h.kind === "resumed" && name === "Approval") resumed = h;
    if (h.kind === "workflow.rejected" && name === "Approval") rejected = h;
  });
  return {
    name: name as typeof stepNames[number],
    started: stepStart, completed: stepEnd, failed: stepFailed,
    suspended, resumed, rejected, executors, blocked,
  };
}

export default function OrchestrationView({ workflowId }: { workflowId: string }) {
  const [data, setData] = useState<OrchestrationData | null>(null);

  useEffect(() => {
    const tick = () => void fetch(`/api/workflows/${workflowId}/orchestration`)
      .then(r => r.ok ? r.json() : null)
      .then(setData);
    tick();
    const i = setInterval(tick, 1500);
    return () => clearInterval(i);
  }, [workflowId]);

  if (!data) return <div className="text-xs text-slate-500">loading orchestration…</div>;

  const stepViews = stepNames.map(name => deriveStepView(data.history, name));

  return (
    <div className="space-y-3 text-xs">
      <div className="border border-slate-800 rounded p-3 bg-slate-900/30">
        <div>Durable Workflow: <span className="text-slate-200">InvoiceP2POrchestrator</span></div>
        <div>instance: <span className="text-slate-300 font-mono">{data.instance_id || "—"}</span></div>
        <div>status: <span className="text-slate-200">{data.status}</span></div>
      </div>
      <div className="space-y-2">
        {stepViews.map(s => (
          <div key={s.name} className="border border-slate-800 rounded bg-slate-900/30">
            <div className="px-3 py-1.5 flex items-center gap-2">
              <div className="w-32 text-slate-200">{s.name}</div>
              {s.rejected ? <div className="text-red-400">✗ rejected</div>
                : s.failed ? <div className="text-red-400">✗ failed</div>
                : s.completed ? <div className="text-emerald-400">✓ completed</div>
                : s.suspended && !s.resumed ? <div className="text-amber-400">⏸ suspended</div>
                : s.blocked ? <div className="text-red-400">✗ blocked</div>
                : s.started ? <div className="text-blue-400">running</div>
                : <div className="text-slate-500">not started</div>}
              {s.completed?.payload?.duration_ms != null && (
                <div className="text-slate-500 ml-auto">{s.completed.payload.duration_ms} ms</div>
              )}
            </div>
            {(s.executors.length > 0 || s.blocked || s.suspended || s.rejected) && (
              <div className="border-t border-slate-800 px-3 py-2 space-y-0.5">
                {s.executors.map((e, i) => (
                  <div key={i} className="flex items-center gap-2 text-[11px]">
                    {exTypeLabel(e.payload.type)}
                    <span className="text-slate-300 font-mono">{e.payload.name}</span>
                    <span className="text-slate-500 ml-auto">{e.payload.duration_ms} ms</span>
                  </div>
                ))}
                {s.blocked && (
                  <div className="text-red-400 mt-1">
                    ↳ {String(s.blocked.payload.name ?? "")} blocked: {String(s.blocked.payload.reason ?? "")} → routed to Fleet Manager
                  </div>
                )}
                {s.suspended && !s.resumed && (
                  <div className="text-amber-300 mt-1">↳ awaiting `approval_decision` (zero compute)</div>
                )}
                {s.resumed && (
                  <div className="text-emerald-300 mt-1">↳ resumed with operator decision</div>
                )}
                {s.rejected && (
                  <div className="text-red-400 mt-1">
                    ↳ rejected by {String(s.rejected.payload.by ?? "operator")}
                    {s.rejected.payload.reason ? ` (${String(s.rejected.payload.reason)})` : ""}
                  </div>
                )}
                {s.failed?.payload?.error && (
                  <div className="text-red-400 mt-1">↳ error: {String(s.failed.payload.error)}</div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

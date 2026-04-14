// src/client/components/FleetManagerRail.tsx
import { useState } from "react";
import { useFleetManagerStream } from "../hooks/useFleetManagerStream";
import { useOrchestrationStream } from "../hooks/useOrchestrationStream";
import { Activity, Loader2, Wrench, CheckCircle2, AlertCircle } from "lucide-react";

const fmIconFor = (kind: string) => {
  switch (kind) {
    case "wakeup": return <Activity size={14} className="text-amber-400" />;
    case "reasoning_start": return <Loader2 size={14} className="text-blue-400 animate-spin" />;
    case "tool_call": return <Wrench size={14} className="text-purple-300" />;
    case "reasoning_done": return <CheckCircle2 size={14} className="text-emerald-400" />;
    case "error": return <AlertCircle size={14} className="text-red-400" />;
    default: return <Activity size={14} className="text-slate-400" />;
  }
};

const orchTypeIcon = (t: string | undefined) => {
  if (t === "agent") return <span className="text-purple-300 text-[10px] font-mono">[agt]</span>;
  if (t === "validator") return <span className="text-amber-300 text-[10px] font-mono">[val]</span>;
  if (t === "deterministic") return <span className="text-slate-400 text-[10px] font-mono">[det]</span>;
  return <span className="text-slate-500 text-[10px] font-mono">[stp]</span>;
};

const orchSummary = (e: { kind: string; payload: { name?: string; stage?: string; step?: string } }) => {
  if (e.kind === "executor.invoked") return `${e.payload.name} (${e.payload.stage})`;
  if (e.kind.startsWith("step.")) return `step:${e.payload.step} ${e.kind.split(".")[1]}`;
  if (e.kind.startsWith("workflow.")) return `workflow ${e.kind.split(".")[1]}`;
  if (e.kind === "validator.blocked") return `${e.payload.name} BLOCKED`;
  if (e.kind === "suspended") return `suspended (HITL)`;
  if (e.kind === "resumed") return `resumed`;
  return e.kind;
};

export default function FleetManagerRail() {
  const fmEvents = useFleetManagerStream();
  const orchEvents = useOrchestrationStream();
  const [tab, setTab] = useState<"fm" | "orch">("fm");

  return (
    <div className="p-3 space-y-2">
      <div className="flex gap-1 border-b border-slate-800 mb-1">
        <button
          onClick={() => setTab("fm")}
          className={`text-[11px] px-2 py-1 ${tab === "fm" ? "text-slate-100 border-b-2 border-blue-400" : "text-slate-400"}`}
        >
          Fleet Manager
        </button>
        <button
          onClick={() => setTab("orch")}
          className={`text-[11px] px-2 py-1 ${tab === "orch" ? "text-slate-100 border-b-2 border-blue-400" : "text-slate-400"}`}
        >
          Orchestration
        </button>
      </div>
      {tab === "fm" && (
        <div className="space-y-1.5">
          <div className="text-[11px] text-slate-500">GHCP SDK session · {fmEvents.length} recent events</div>
          {fmEvents.length === 0 && <div className="text-xs text-slate-500">idle</div>}
          {fmEvents.map((e, i) => (
            <div key={i} className="flex gap-2 text-xs border border-slate-800 rounded p-2">
              {fmIconFor(e.kind)}
              <div className="flex-1 min-w-0">
                <div className="text-slate-200 font-medium truncate">{e.kind}</div>
                <div className="text-[11px] text-slate-500 truncate">
                  {e.data ? JSON.stringify(e.data).slice(0, 160) : ""}
                </div>
              </div>
              <div className="text-[10px] text-slate-600 whitespace-nowrap">
                {new Date(e.timestamp).toLocaleTimeString()}
              </div>
            </div>
          ))}
        </div>
      )}
      {tab === "orch" && (
        <div className="space-y-1">
          <div className="text-[11px] text-slate-500">MAF Durable Workflows · {orchEvents.length} recent events</div>
          {orchEvents.length === 0 && <div className="text-xs text-slate-500">idle</div>}
          {orchEvents.map((e, i) => (
            <div key={i} className="flex items-center gap-2 text-[11px] border border-slate-800 rounded px-2 py-1">
              {orchTypeIcon(e.payload.type)}
              <span className="text-slate-300 font-mono truncate">{e.workflow_id}</span>
              <span className="text-slate-200 truncate flex-1">{orchSummary(e)}</span>
              {e.payload.duration_ms != null && <span className="text-slate-500">{e.payload.duration_ms} ms</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

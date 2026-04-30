// src/client/components/FleetManagerRail.tsx
import { useState } from "react";
import { useFleetManagerStream } from "../hooks/useFleetManagerStream";
import { useOrchestrationStream } from "../hooks/useOrchestrationStream";
import { Activity, Loader2, Wrench, CheckCircle2, AlertCircle } from "lucide-react";

const summarizeFm = (kind: string, data: unknown): string => {
  if (data == null || typeof data !== "object") return "";
  const d = data as Record<string, unknown>;
  const wfIds = Array.isArray(d.workflow_ids) ? (d.workflow_ids as string[]).join(", ") : undefined;
  const wfId = typeof d.workflow_id === "string" ? d.workflow_id : undefined;
  const tool = typeof d.tool === "string" ? d.tool : typeof d.name === "string" ? d.name : undefined;
  const reason = typeof d.reason === "string" ? d.reason : undefined;
  if (kind === "wakeup") return `${wfId ?? "?"}${reason ? ` · ${reason}` : ""}`;
  if (kind === "reasoning_start" || kind === "reasoning_done") {
    const batch = typeof d.batch_size === "number" ? `${d.batch_size}` : undefined;
    return [wfIds, batch ? `batch ${batch}` : null].filter(Boolean).join(" · ");
  }
  if (kind === "tool_call") return tool ?? "";
  if (kind === "error") return typeof d.error === "string" ? d.error : "";
  return wfId ?? wfIds ?? "";
};

const fmIconFor = (kind: string) => {
  switch (kind) {
    case "wakeup": return <Activity size={14} className="text-amber-600" />;
    case "reasoning_start": return <Loader2 size={14} className="text-blue-600 animate-spin" />;
    case "tool_call": return <Wrench size={14} className="text-purple-600" />;
    case "reasoning_done": return <CheckCircle2 size={14} className="text-emerald-600" />;
    case "error": return <AlertCircle size={14} className="text-red-600" />;
    default: return <Activity size={14} className="text-slate-400" />;
  }
};

const orchTypeIcon = (t: string | undefined) => {
  if (t === "agent") return <span className="text-purple-700 text-[10px] font-mono">[agt]</span>;
  if (t === "validator") return <span className="text-amber-700 text-[10px] font-mono">[val]</span>;
  if (t === "deterministic") return <span className="text-slate-500 text-[10px] font-mono">[det]</span>;
  return <span className="text-slate-400 text-[10px] font-mono">[stp]</span>;
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
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const toggle = (i: number) => setExpanded(prev => {
    const next = new Set(prev);
    next.has(i) ? next.delete(i) : next.add(i);
    return next;
  });

  return (
    <div className="p-3 space-y-2">
      <div className="flex gap-1 border-b border-slate-200 mb-2">
        <button
          onClick={() => setTab("fm")}
          className={`text-[11px] px-2 py-1 ${tab === "fm" ? "text-blue-700 font-medium border-b-2 border-blue-600" : "text-slate-500 hover:text-slate-700"}`}
        >
          Fleet Manager
        </button>
        <button
          onClick={() => setTab("orch")}
          className={`text-[11px] px-2 py-1 ${tab === "orch" ? "text-blue-700 font-medium border-b-2 border-blue-600" : "text-slate-500 hover:text-slate-700"}`}
        >
          Orchestration
        </button>
      </div>
      {tab === "fm" && (
        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
            <span className="relative flex h-1.5 w-1.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500"></span>
            </span>
            <span>GHCP SDK session · {fmEvents.length} recent events</span>
          </div>
          {fmEvents.length === 0 && (
            <div className="text-xs text-slate-500 italic px-2 py-3 border border-dashed border-slate-200 rounded">
              Watching event bus. Fleet Manager will compose summaries when workflows need attention.
            </div>
          )}
          {fmEvents.map((e, i) => {
            const open = expanded.has(i);
            return (
              <div key={i} className="text-xs border border-slate-200 rounded bg-white">
                <button
                  type="button"
                  onClick={() => toggle(i)}
                  className="w-full flex gap-2 p-2 text-left hover:bg-slate-50"
                >
                  {fmIconFor(e.kind)}
                  <div className="flex-1 min-w-0">
                    <div className="text-slate-800 font-medium truncate">{e.kind}</div>
                    <div className={`text-[11px] text-slate-500 ${open ? "" : "truncate"}`}>
                      {open ? "tap to collapse" : summarizeFm(e.kind, e.data)}
                    </div>
                  </div>
                  <div className="text-[10px] text-slate-400 whitespace-nowrap">
                    {new Date(e.timestamp).toLocaleTimeString()}
                  </div>
                </button>
                {open && e.data != null && (
                  <pre className="text-[10px] text-slate-700 bg-slate-50 p-2 border-t border-slate-200 whitespace-pre-wrap break-all max-h-96 overflow-auto">
{JSON.stringify(e.data, null, 2)}
                  </pre>
                )}
              </div>
            );
          })}
        </div>
      )}
      {tab === "orch" && (
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
            <span className="relative flex h-1.5 w-1.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-blue-500"></span>
            </span>
            <span>Durable Functions · {orchEvents.length} recent events</span>
          </div>
          {orchEvents.length === 0 && (
            <div className="text-xs text-slate-500 italic px-2 py-3 border border-dashed border-slate-200 rounded">
              Watching orchestration bus. Phase activity will appear here as workflows advance.
            </div>
          )}
          {orchEvents.map((e, i) => (
            <div key={i} className="flex items-center gap-2 text-[11px] border border-slate-200 rounded px-2 py-1 bg-white">
              {orchTypeIcon(e.payload.type)}
              <span className="text-slate-700 font-mono truncate">{e.workflow_id}</span>
              <span className="text-slate-800 truncate flex-1">{orchSummary(e)}</span>
              {e.payload.duration_ms != null && <span className="text-slate-400">{e.payload.duration_ms} ms</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// src/client/components/FleetManagerRail.tsx
import { useFleetManagerStream } from "../hooks/useFleetManagerStream";
import { Activity, Loader2, Wrench, CheckCircle2, AlertCircle } from "lucide-react";

const iconFor = (kind: string) => {
  switch (kind) {
    case "wakeup":
      return <Activity size={14} className="text-amber-400" />;
    case "reasoning_start":
      return <Loader2 size={14} className="text-blue-400 animate-spin" />;
    case "tool_call":
      return <Wrench size={14} className="text-purple-300" />;
    case "reasoning_done":
      return <CheckCircle2 size={14} className="text-emerald-400" />;
    case "error":
      return <AlertCircle size={14} className="text-red-400" />;
    default:
      return <Activity size={14} className="text-slate-400" />;
  }
};

export default function FleetManagerRail() {
  const events = useFleetManagerStream();
  return (
    <div className="p-3 space-y-2">
      <div className="text-xs uppercase tracking-wider text-slate-400">Fleet Manager</div>
      <div className="text-[11px] text-slate-500">
        GHCP SDK session · {events.length} recent events
      </div>
      <div className="space-y-1.5">
        {events.length === 0 && <div className="text-xs text-slate-500">idle</div>}
        {events.map((e, i) => (
          <div key={i} className="flex gap-2 text-xs border border-slate-800 rounded p-2">
            {iconFor(e.kind)}
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
    </div>
  );
}

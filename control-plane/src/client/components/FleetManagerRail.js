import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// src/client/components/FleetManagerRail.tsx
import { useState } from "react";
import { useFleetManagerStream } from "../hooks/useFleetManagerStream";
import { useOrchestrationStream } from "../hooks/useOrchestrationStream";
import { Activity, Loader2, Wrench, CheckCircle2, AlertCircle } from "lucide-react";
const fmIconFor = (kind) => {
    switch (kind) {
        case "wakeup": return _jsx(Activity, { size: 14, className: "text-amber-400" });
        case "reasoning_start": return _jsx(Loader2, { size: 14, className: "text-blue-400 animate-spin" });
        case "tool_call": return _jsx(Wrench, { size: 14, className: "text-purple-300" });
        case "reasoning_done": return _jsx(CheckCircle2, { size: 14, className: "text-emerald-400" });
        case "error": return _jsx(AlertCircle, { size: 14, className: "text-red-400" });
        default: return _jsx(Activity, { size: 14, className: "text-slate-400" });
    }
};
const orchTypeIcon = (t) => {
    if (t === "agent")
        return _jsx("span", { className: "text-purple-300 text-[10px] font-mono", children: "[agt]" });
    if (t === "validator")
        return _jsx("span", { className: "text-amber-300 text-[10px] font-mono", children: "[val]" });
    if (t === "deterministic")
        return _jsx("span", { className: "text-slate-400 text-[10px] font-mono", children: "[det]" });
    return _jsx("span", { className: "text-slate-500 text-[10px] font-mono", children: "[stp]" });
};
const orchSummary = (e) => {
    if (e.kind === "executor.invoked")
        return `${e.payload.name} (${e.payload.stage})`;
    if (e.kind.startsWith("step."))
        return `step:${e.payload.step} ${e.kind.split(".")[1]}`;
    if (e.kind.startsWith("workflow."))
        return `workflow ${e.kind.split(".")[1]}`;
    if (e.kind === "validator.blocked")
        return `${e.payload.name} BLOCKED`;
    if (e.kind === "suspended")
        return `suspended (HITL)`;
    if (e.kind === "resumed")
        return `resumed`;
    return e.kind;
};
export default function FleetManagerRail() {
    const fmEvents = useFleetManagerStream();
    const orchEvents = useOrchestrationStream();
    const [tab, setTab] = useState("fm");
    return (_jsxs("div", { className: "p-3 space-y-2", children: [_jsxs("div", { className: "flex gap-1 border-b border-slate-800 mb-1", children: [_jsx("button", { onClick: () => setTab("fm"), className: `text-[11px] px-2 py-1 ${tab === "fm" ? "text-slate-100 border-b-2 border-blue-400" : "text-slate-400"}`, children: "Fleet Manager" }), _jsx("button", { onClick: () => setTab("orch"), className: `text-[11px] px-2 py-1 ${tab === "orch" ? "text-slate-100 border-b-2 border-blue-400" : "text-slate-400"}`, children: "Orchestration" })] }), tab === "fm" && (_jsxs("div", { className: "space-y-1.5", children: [_jsxs("div", { className: "text-[11px] text-slate-500", children: ["GHCP SDK session \u00B7 ", fmEvents.length, " recent events"] }), fmEvents.length === 0 && _jsx("div", { className: "text-xs text-slate-500", children: "idle" }), fmEvents.map((e, i) => (_jsxs("div", { className: "flex gap-2 text-xs border border-slate-800 rounded p-2", children: [fmIconFor(e.kind), _jsxs("div", { className: "flex-1 min-w-0", children: [_jsx("div", { className: "text-slate-200 font-medium truncate", children: e.kind }), _jsx("div", { className: "text-[11px] text-slate-500 truncate", children: e.data ? JSON.stringify(e.data).slice(0, 160) : "" })] }), _jsx("div", { className: "text-[10px] text-slate-600 whitespace-nowrap", children: new Date(e.timestamp).toLocaleTimeString() })] }, i)))] })), tab === "orch" && (_jsxs("div", { className: "space-y-1", children: [_jsxs("div", { className: "text-[11px] text-slate-500", children: ["MAF Durable Workflows \u00B7 ", orchEvents.length, " recent events"] }), orchEvents.length === 0 && _jsx("div", { className: "text-xs text-slate-500", children: "idle" }), orchEvents.map((e, i) => (_jsxs("div", { className: "flex items-center gap-2 text-[11px] border border-slate-800 rounded px-2 py-1", children: [orchTypeIcon(e.payload.type), _jsx("span", { className: "text-slate-300 font-mono truncate", children: e.workflow_id }), _jsx("span", { className: "text-slate-200 truncate flex-1", children: orchSummary(e) }), e.payload.duration_ms != null && _jsxs("span", { className: "text-slate-500", children: [e.payload.duration_ms, " ms"] })] }, i)))] }))] }));
}

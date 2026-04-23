import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// src/client/components/FleetManagerRail.tsx
import { useState } from "react";
import { useFleetManagerStream } from "../hooks/useFleetManagerStream";
import { useOrchestrationStream } from "../hooks/useOrchestrationStream";
import { Activity, Loader2, Wrench, CheckCircle2, AlertCircle } from "lucide-react";
const summarizeFm = (kind, data) => {
    if (data == null || typeof data !== "object")
        return "";
    const d = data;
    const wfIds = Array.isArray(d.workflow_ids) ? d.workflow_ids.join(", ") : undefined;
    const wfId = typeof d.workflow_id === "string" ? d.workflow_id : undefined;
    const tool = typeof d.tool === "string" ? d.tool : typeof d.name === "string" ? d.name : undefined;
    const reason = typeof d.reason === "string" ? d.reason : undefined;
    if (kind === "wakeup")
        return `${wfId ?? "?"}${reason ? ` · ${reason}` : ""}`;
    if (kind === "reasoning_start" || kind === "reasoning_done") {
        const batch = typeof d.batch_size === "number" ? `${d.batch_size}` : undefined;
        return [wfIds, batch ? `batch ${batch}` : null].filter(Boolean).join(" · ");
    }
    if (kind === "tool_call")
        return tool ?? "";
    if (kind === "error")
        return typeof d.error === "string" ? d.error : "";
    return wfId ?? wfIds ?? "";
};
const fmIconFor = (kind) => {
    switch (kind) {
        case "wakeup": return _jsx(Activity, { size: 14, className: "text-amber-600" });
        case "reasoning_start": return _jsx(Loader2, { size: 14, className: "text-blue-600 animate-spin" });
        case "tool_call": return _jsx(Wrench, { size: 14, className: "text-purple-600" });
        case "reasoning_done": return _jsx(CheckCircle2, { size: 14, className: "text-emerald-600" });
        case "error": return _jsx(AlertCircle, { size: 14, className: "text-red-600" });
        default: return _jsx(Activity, { size: 14, className: "text-slate-400" });
    }
};
const orchTypeIcon = (t) => {
    if (t === "agent")
        return _jsx("span", { className: "text-purple-700 text-[10px] font-mono", children: "[agt]" });
    if (t === "validator")
        return _jsx("span", { className: "text-amber-700 text-[10px] font-mono", children: "[val]" });
    if (t === "deterministic")
        return _jsx("span", { className: "text-slate-500 text-[10px] font-mono", children: "[det]" });
    return _jsx("span", { className: "text-slate-400 text-[10px] font-mono", children: "[stp]" });
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
    const [expanded, setExpanded] = useState(new Set());
    const toggle = (i) => setExpanded(prev => {
        const next = new Set(prev);
        next.has(i) ? next.delete(i) : next.add(i);
        return next;
    });
    return (_jsxs("div", { className: "p-3 space-y-2", children: [_jsxs("div", { className: "flex gap-1 border-b border-slate-200 mb-2", children: [_jsx("button", { onClick: () => setTab("fm"), className: `text-[11px] px-2 py-1 ${tab === "fm" ? "text-blue-700 font-medium border-b-2 border-blue-600" : "text-slate-500 hover:text-slate-700"}`, children: "Fleet Manager" }), _jsx("button", { onClick: () => setTab("orch"), className: `text-[11px] px-2 py-1 ${tab === "orch" ? "text-blue-700 font-medium border-b-2 border-blue-600" : "text-slate-500 hover:text-slate-700"}`, children: "Orchestration" })] }), tab === "fm" && (_jsxs("div", { className: "space-y-1.5", children: [_jsxs("div", { className: "text-[11px] text-slate-500", children: ["GHCP SDK session \u00B7 ", fmEvents.length, " recent events"] }), fmEvents.length === 0 && _jsx("div", { className: "text-xs text-slate-400 italic", children: "idle" }), fmEvents.map((e, i) => {
                        const open = expanded.has(i);
                        return (_jsxs("div", { className: "text-xs border border-slate-200 rounded bg-white", children: [_jsxs("button", { type: "button", onClick: () => toggle(i), className: "w-full flex gap-2 p-2 text-left hover:bg-slate-50", children: [fmIconFor(e.kind), _jsxs("div", { className: "flex-1 min-w-0", children: [_jsx("div", { className: "text-slate-800 font-medium truncate", children: e.kind }), _jsx("div", { className: `text-[11px] text-slate-500 ${open ? "" : "truncate"}`, children: open ? "tap to collapse" : summarizeFm(e.kind, e.data) })] }), _jsx("div", { className: "text-[10px] text-slate-400 whitespace-nowrap", children: new Date(e.timestamp).toLocaleTimeString() })] }), open && e.data != null && (_jsx("pre", { className: "text-[10px] text-slate-700 bg-slate-50 p-2 border-t border-slate-200 whitespace-pre-wrap break-all max-h-96 overflow-auto", children: JSON.stringify(e.data, null, 2) }))] }, i));
                    })] })), tab === "orch" && (_jsxs("div", { className: "space-y-1", children: [_jsxs("div", { className: "text-[11px] text-slate-500", children: ["MAF Durable Workflows \u00B7 ", orchEvents.length, " recent events"] }), orchEvents.length === 0 && _jsx("div", { className: "text-xs text-slate-400 italic", children: "idle" }), orchEvents.map((e, i) => (_jsxs("div", { className: "flex items-center gap-2 text-[11px] border border-slate-200 rounded px-2 py-1 bg-white", children: [orchTypeIcon(e.payload.type), _jsx("span", { className: "text-slate-700 font-mono truncate", children: e.workflow_id }), _jsx("span", { className: "text-slate-800 truncate flex-1", children: orchSummary(e) }), e.payload.duration_ms != null && _jsxs("span", { className: "text-slate-400", children: [e.payload.duration_ms, " ms"] })] }, i)))] }))] }));
}

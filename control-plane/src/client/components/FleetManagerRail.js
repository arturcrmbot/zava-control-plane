import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// src/client/components/FleetManagerRail.tsx
import { useFleetManagerStream } from "../hooks/useFleetManagerStream";
import { Activity, Loader2, Wrench, CheckCircle2, AlertCircle } from "lucide-react";
const iconFor = (kind) => {
    switch (kind) {
        case "wakeup":
            return _jsx(Activity, { size: 14, className: "text-amber-400" });
        case "reasoning_start":
            return _jsx(Loader2, { size: 14, className: "text-blue-400 animate-spin" });
        case "tool_call":
            return _jsx(Wrench, { size: 14, className: "text-purple-300" });
        case "reasoning_done":
            return _jsx(CheckCircle2, { size: 14, className: "text-emerald-400" });
        case "error":
            return _jsx(AlertCircle, { size: 14, className: "text-red-400" });
        default:
            return _jsx(Activity, { size: 14, className: "text-slate-400" });
    }
};
export default function FleetManagerRail() {
    const events = useFleetManagerStream();
    return (_jsxs("div", { className: "p-3 space-y-2", children: [_jsx("div", { className: "text-xs uppercase tracking-wider text-slate-400", children: "Fleet Manager" }), _jsxs("div", { className: "text-[11px] text-slate-500", children: ["GHCP SDK session \u00B7 ", events.length, " recent events"] }), _jsxs("div", { className: "space-y-1.5", children: [events.length === 0 && _jsx("div", { className: "text-xs text-slate-500", children: "idle" }), events.map((e, i) => (_jsxs("div", { className: "flex gap-2 text-xs border border-slate-800 rounded p-2", children: [iconFor(e.kind), _jsxs("div", { className: "flex-1 min-w-0", children: [_jsx("div", { className: "text-slate-200 font-medium truncate", children: e.kind }), _jsx("div", { className: "text-[11px] text-slate-500 truncate", children: e.data ? JSON.stringify(e.data).slice(0, 160) : "" })] }), _jsx("div", { className: "text-[10px] text-slate-600 whitespace-nowrap", children: new Date(e.timestamp).toLocaleTimeString() })] }, i)))] })] }));
}

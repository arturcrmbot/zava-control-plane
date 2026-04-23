import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// src/client/components/PhaseTimeline.tsx
import { PHASE_ORDER } from "@shared/types";
const STATUS_LABEL = {
    not_started: "pending",
    pending: "pending",
    in_progress: "in progress",
    completed: "completed",
    failed: "failed",
};
const STATUS_STYLE = {
    completed: "text-emerald-700",
    in_progress: "text-blue-700",
    failed: "text-red-700",
    pending: "text-slate-400",
    not_started: "text-slate-400",
};
export default function PhaseTimeline({ phases }) {
    const byName = new Map(phases.map(p => [p.name, p]));
    return (_jsx("div", { className: "space-y-1.5", children: PHASE_ORDER.map(name => {
            const p = byName.get(name);
            const status = p?.status ?? "not_started";
            const duration = p?.startedAt && p?.completedAt ? Math.round(p.completedAt - p.startedAt) : null;
            const tools = p?.toolCalls.length ?? 0;
            return (_jsxs("div", { className: "flex items-center gap-3 text-xs bg-white border border-slate-200 rounded px-3 py-2", children: [_jsx("div", { className: `w-32 font-medium ${p ? "text-slate-800" : "text-slate-400"}`, children: name }), _jsx("div", { className: `text-[10px] uppercase tracking-wide font-medium ${STATUS_STYLE[status]}`, children: STATUS_LABEL[status] }), duration != null && _jsxs("div", { className: "text-slate-500", children: [duration, " ms"] }), _jsxs("div", { className: "ml-auto text-slate-500", children: [tools, " tool", tools === 1 ? "" : "s"] })] }, name));
        }) }));
}

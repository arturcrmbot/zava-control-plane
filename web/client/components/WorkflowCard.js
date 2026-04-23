import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Link } from "react-router-dom";
import { PHASE_ORDER } from "@shared/types";
const statusColor = {
    in_progress: "text-blue-700", awaiting_hitl: "text-amber-700",
    completed: "text-emerald-700", failed: "text-red-700"
};
export default function WorkflowCard({ w }) {
    const phaseIdx = PHASE_ORDER.indexOf(w.currentPhase);
    const pct = ((phaseIdx + 1) / PHASE_ORDER.length) * 100;
    return (_jsxs(Link, { to: `/workflows/${w.id}`, className: "block bg-white border border-slate-200 rounded-lg p-3 shadow-sm hover:border-blue-300 hover:shadow transition", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx("div", { className: "font-medium text-sm text-slate-900", children: w.id }), _jsx("div", { className: `text-[10px] uppercase tracking-wide font-medium ${statusColor[w.status]}`, children: w.status })] }), _jsx("div", { className: "text-xs text-slate-500 mt-0.5 truncate", children: w.vendor.name }), _jsxs("div", { className: "text-xs text-slate-700 mt-1 font-medium", children: [w.invoice.currency, " ", w.invoice.amount.toLocaleString()] }), _jsx("div", { className: "mt-2 text-[10px] text-slate-500", children: w.currentPhase }), _jsx("div", { className: "h-1 bg-slate-100 rounded mt-1", children: _jsx("div", { className: "h-1 bg-blue-500 rounded", style: { width: `${pct}%` } }) }), w.activeExceptionId && (_jsx("div", { className: "mt-2 text-[10px] text-amber-700 font-medium", children: "\u26A0 exception" }))] }));
}

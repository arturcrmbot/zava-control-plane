import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Link } from "react-router-dom";
import { PHASE_ORDER } from "@shared/types";
const statusColor = {
    in_progress: "text-blue-400", awaiting_hitl: "text-amber-400",
    completed: "text-emerald-400", failed: "text-red-400"
};
export default function WorkflowCard({ w }) {
    const phaseIdx = PHASE_ORDER.indexOf(w.currentPhase);
    const pct = ((phaseIdx + 1) / PHASE_ORDER.length) * 100;
    return (_jsxs(Link, { to: `/workflows/${w.id}`, className: "block border border-slate-800 rounded p-3 hover:border-slate-700 bg-slate-900/50", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx("div", { className: "font-medium text-sm", children: w.id }), _jsx("div", { className: `text-[10px] uppercase ${statusColor[w.status]}`, children: w.status })] }), _jsx("div", { className: "text-xs text-slate-400 mt-0.5 truncate", children: w.vendor.name }), _jsxs("div", { className: "text-xs text-slate-300 mt-1", children: [w.invoice.currency, " ", w.invoice.amount.toLocaleString()] }), _jsx("div", { className: "mt-2 text-[10px] text-slate-500", children: w.currentPhase }), _jsx("div", { className: "h-1 bg-slate-800 rounded mt-1", children: _jsx("div", { className: "h-1 bg-blue-400 rounded", style: { width: `${pct}%` } }) }), w.activeExceptionId && (_jsx("div", { className: "mt-2 text-[10px] text-amber-400", children: "\u26A0 exception" }))] }));
}

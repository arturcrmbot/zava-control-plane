import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
function riskFactor(w) {
    const hrsToSLA = (w.slaDueAt - Date.now() / 1000) / 3600;
    const hasExc = !!w.activeExceptionId;
    if (hasExc && hrsToSLA < 24)
        return "high";
    if (hasExc || hrsToSLA < 48)
        return "medium";
    return "low";
}
function slaHealth(w) {
    const hrs = Math.max(0, (w.slaDueAt - Date.now() / 1000) / 3600);
    if (hrs >= 24)
        return `${Math.round(hrs / 24)}d remaining`;
    return `${Math.round(hrs)}h remaining`;
}
const RISK_COLOR = {
    low: "text-emerald-700 bg-emerald-50 border-emerald-200",
    medium: "text-amber-700 bg-amber-50 border-amber-200",
    high: "text-red-700 bg-red-50 border-red-200",
};
const STATUS_HUMAN = {
    in_progress: "In progress",
    awaiting_hitl: "Awaiting operator",
    completed: "Completed",
    failed: "Failed",
};
const STATUS_COLOR = {
    in_progress: "text-blue-700 bg-blue-50 border-blue-200",
    awaiting_hitl: "text-amber-700 bg-amber-50 border-amber-200",
    completed: "text-emerald-700 bg-emerald-50 border-emerald-200",
    failed: "text-red-700 bg-red-50 border-red-200",
};
export default function WorkflowHeaderTiles({ workflow }) {
    const risk = riskFactor(workflow);
    const stalled = !!workflow.activeExceptionId;
    const statusTile = stalled
        ? { label: "STATUS · STALLED", value: `Exception at ${workflow.currentPhase}`, cls: "text-red-700 bg-red-50 border-red-200" }
        : { label: "STATUS", value: STATUS_HUMAN[workflow.status], cls: STATUS_COLOR[workflow.status] };
    return (_jsx("div", { className: "grid grid-cols-3 gap-3", "data-testid": "workflow-header-tiles", children: [
            statusTile,
            { label: "SLA HEALTH", value: slaHealth(workflow), cls: "text-slate-700 bg-slate-50 border-slate-200" },
            { label: "RISK FACTOR", value: risk.toUpperCase(), cls: RISK_COLOR[risk] },
        ].map(t => (_jsxs("div", { className: `rounded-lg border p-3 ${t.cls}`, children: [_jsx("div", { className: "text-[10px] uppercase font-semibold tracking-wide opacity-70", children: t.label }), _jsx("div", { className: "text-base font-semibold mt-1", children: t.value })] }, t.label))) }));
}

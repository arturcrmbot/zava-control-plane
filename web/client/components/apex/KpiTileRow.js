import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export default function KpiTileRow({ workflows, exceptionsCount }) {
    const tiles = [
        { label: "Active Runs", v: workflows.filter(w => w.status === "in_progress").length },
        { label: "Awaiting HITL", v: workflows.filter(w => w.status === "awaiting_hitl").length },
        { label: "Completed", v: workflows.filter(w => w.status === "completed").length },
        { label: "Failed", v: workflows.filter(w => w.status === "failed").length },
        { label: "Exceptions", v: exceptionsCount },
    ];
    return (_jsx("div", { className: "grid grid-cols-5 gap-3", "data-testid": "kpi-tile-row", children: tiles.map(t => (_jsxs("div", { className: "panel panel-body", children: [_jsx("div", { className: "text-[10px] uppercase tracking-wide text-slate-500", children: t.label }), _jsx("div", { className: "text-2xl font-semibold text-slate-900 mt-1", children: t.v })] }, t.label))) }));
}

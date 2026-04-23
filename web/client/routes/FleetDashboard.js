import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// src/client/routes/FleetDashboard.tsx
import { useWorkflows } from "../hooks/useWorkflows";
import { useExceptions } from "../hooks/useExceptions";
import WorkflowCard from "../components/WorkflowCard";
import DevPanel from "../components/DevPanel";
import KpiTileRow from "../components/apex/KpiTileRow";
import ExceptionCardCompact from "../components/apex/ExceptionCardCompact";
import FleetEconomicsPanel from "../components/apex/FleetEconomicsPanel";
import PolicyAutonomyPanel from "../components/apex/PolicyAutonomyPanel";
export default function FleetDashboard() {
    const workflows = useWorkflows();
    const { items: exceptions } = useExceptions();
    const topExceptions = exceptions.slice(0, 3);
    return (_jsxs("div", { className: "grid grid-cols-4 gap-4 min-w-0", children: [_jsxs("div", { className: "col-span-3 space-y-4 min-w-0", children: [_jsxs("div", { className: "flex items-center gap-3", children: [_jsxs("div", { children: [_jsx("div", { className: "text-xl font-semibold text-slate-900", children: "Control Plane Overview" }), _jsx("div", { className: "text-xs text-slate-500", children: "Operational status for Finance Controller's fleet" })] }), _jsx("div", { className: "ml-auto", children: _jsx(DevPanel, {}) })] }), _jsx(KpiTileRow, { workflows: workflows, exceptionsCount: exceptions.length }), _jsxs("div", { className: "panel", children: [_jsx("div", { className: "panel-header", children: "Exceptions Requiring Attention" }), _jsxs("div", { className: "panel-body grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3", children: [topExceptions.length === 0 &&
                                        _jsx("div", { className: "text-xs text-slate-500 col-span-full italic", children: "No open exceptions." }), topExceptions.map(e => _jsx(ExceptionCardCompact, { e: e }, e.id))] })] }), _jsxs("div", { className: "panel", children: [_jsxs("div", { className: "panel-header flex items-center justify-between", children: [_jsx("span", { children: "Active Workflows" }), _jsxs("span", { className: "text-[11px] text-slate-500", children: [workflows.length, " shown"] })] }), _jsxs("div", { className: "panel-body grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-3", children: [workflows.length === 0 && (_jsx("div", { className: "text-xs text-slate-500 italic col-span-full", children: "No active workflows." })), workflows.map(w => _jsx(WorkflowCard, { w: w }, w.id))] })] })] }), _jsxs("div", { className: "col-span-1 space-y-3", children: [_jsx(FleetEconomicsPanel, {}), _jsx(PolicyAutonomyPanel, {})] })] }));
}

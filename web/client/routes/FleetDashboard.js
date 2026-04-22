import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// src/client/routes/FleetDashboard.tsx
import { useMemo, useState } from "react";
import { useWorkflows } from "../hooks/useWorkflows";
import WorkflowCard from "../components/WorkflowCard";
import DevPanel from "../components/DevPanel";
export default function FleetDashboard() {
    const workflows = useWorkflows();
    const [phaseFilter, setPhaseFilter] = useState("");
    const [agencyFilter, setAgencyFilter] = useState("");
    const [exceptionsOnly, setExceptionsOnly] = useState(false);
    const filtered = useMemo(() => workflows.filter(w => (!phaseFilter || w.currentPhase === phaseFilter) &&
        (!agencyFilter || w.agency === agencyFilter) &&
        (!exceptionsOnly || !!w.activeExceptionId)), [workflows, phaseFilter, agencyFilter, exceptionsOnly]);
    const counts = {
        total: workflows.length,
        inFlight: workflows.filter(w => w.status === "in_progress").length,
        awaiting: workflows.filter(w => w.status === "awaiting_hitl").length,
        completed: workflows.filter(w => w.status === "completed").length,
        exceptions: workflows.filter(w => w.activeExceptionId).length
    };
    const agencies = Array.from(new Set(workflows.map(w => w.agency))).sort();
    return (_jsxs("div", { className: "space-y-4", children: [_jsx(DevPanel, {}), _jsx("div", { className: "grid grid-cols-5 gap-3", children: Object.entries(counts).map(([k, v]) => (_jsxs("div", { className: "border border-slate-800 rounded p-3 bg-slate-900/50", children: [_jsx("div", { className: "text-[11px] text-slate-500 uppercase", children: k.replace(/([A-Z])/g, " $1") }), _jsx("div", { className: "text-xl font-semibold", children: v })] }, k))) }), _jsxs("div", { className: "flex gap-2 text-sm items-center", children: [_jsxs("select", { value: phaseFilter, onChange: e => setPhaseFilter(e.target.value), className: "bg-slate-900 border border-slate-800 rounded px-2 py-1 text-xs", children: [_jsx("option", { value: "", children: "All phases" }), ["Intake", "Validation", "Routing", "Approval", "Payment", "Reconciliation"].map(p => _jsx("option", { children: p }, p))] }), _jsxs("select", { value: agencyFilter, onChange: e => setAgencyFilter(e.target.value), className: "bg-slate-900 border border-slate-800 rounded px-2 py-1 text-xs", children: [_jsx("option", { value: "", children: "All agencies" }), agencies.map(a => _jsx("option", { children: a }, a))] }), _jsxs("label", { className: "text-xs text-slate-300 flex items-center gap-1", children: [_jsx("input", { type: "checkbox", checked: exceptionsOnly, onChange: e => setExceptionsOnly(e.target.checked) }), "Exceptions only"] }), _jsxs("div", { className: "ml-auto text-xs text-slate-500", children: [filtered.length, " shown"] })] }), _jsx("div", { className: "grid grid-cols-4 gap-2", children: filtered.map(w => _jsx(WorkflowCard, { w: w }, w.id)) })] }));
}

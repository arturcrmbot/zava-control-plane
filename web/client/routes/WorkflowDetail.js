import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
// web/client/routes/WorkflowDetail.tsx
import { useEffect, useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import OtelSpanTree from "../components/OtelSpanTree";
import PhaseTimeline from "../components/PhaseTimeline";
import SkillAmplificationPanel from "../components/SkillAmplificationPanel";
import PhaseRibbon from "../components/apex/PhaseRibbon";
import WorkflowHeaderTiles from "../components/apex/WorkflowHeaderTiles";
import ExceptionAnalysisCard from "../components/apex/ExceptionAnalysisCard";
import InterventionProtocols from "../components/apex/InterventionProtocols";
import EconomicsPanel from "../components/apex/EconomicsPanel";
import FleetAssignment from "../components/apex/FleetAssignment";
import AuditTrail from "../components/apex/AuditTrail";
import ExecutionTimelineTab from "../components/apex/ExecutionTimelineTab";
const TABS = ["Overview", "Phases", "Traces", "Ledger", "Amplification", "Execution Timeline"];
export default function WorkflowDetail() {
    const { id } = useParams();
    const [d, setD] = useState(null);
    const [tab, setTab] = useState("Overview");
    const refresh = useCallback(async () => {
        if (!id)
            return;
        const r = await fetch(`/api/workflows/${id}`);
        setD(await r.json());
    }, [id]);
    useEffect(() => { void refresh(); }, [refresh]);
    const logAction = useCallback(async (action) => {
        if (!id)
            return;
        // Log-only: reuse the existing `workflow.rejected` handler to append an
        // audit-trail entry with the illustrative action name. No other state
        // change happens; Fork/Rollback are visual stubs for the demo.
        await fetch("/internal/durable-event", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                workflow_id: id, kind: "workflow.rejected",
                payload: { by: "operator", reason: `illustrative ${action}` },
            }),
        }).catch(() => { });
        await refresh();
    }, [id, refresh]);
    if (!d)
        return _jsx("div", { className: "text-sm text-slate-500", children: "loading\u2026" });
    const w = d.workflow;
    return (_jsxs("div", { className: "grid grid-cols-4 gap-4", children: [_jsxs("div", { className: "col-span-3 space-y-4", children: [_jsxs("div", { children: [_jsx("div", { className: "text-xs text-slate-500", children: w.id }), _jsxs("div", { className: "text-xl font-semibold", children: [w.id, " \u00B7 ", w.vendor.name] }), _jsxs("div", { className: "text-xs text-slate-500", children: [w.invoice.currency, " ", w.invoice.amount.toLocaleString(), " \u00B7 PO ", w.invoice.poRef, " \u00B7 ", w.agency] })] }), _jsx(WorkflowHeaderTiles, { workflow: w }), _jsx(PhaseRibbon, { workflow: w, phases: d.phases }), _jsx("div", { className: "flex gap-1 border-b border-slate-200", children: TABS.map(t => (_jsx("button", { onClick: () => setTab(t), className: `text-sm px-4 py-2 ${tab === t ?
                                "text-blue-700 border-b-2 border-blue-600 font-medium" :
                                "text-slate-500 hover:text-slate-800"}`, children: t }, t))) }), tab === "Overview" && (_jsxs("div", { className: "space-y-4", children: [d.narrative && d.activeException && (_jsxs(_Fragment, { children: [_jsx(ExceptionAnalysisCard, { narrative: d.narrative }), _jsx(InterventionProtocols, { exception: d.activeException, onResolved: refresh })] })), !d.activeException && (_jsx("div", { className: "panel panel-body text-sm text-slate-500", children: "No active exception. Workflow is progressing autonomously." }))] })), tab === "Phases" && _jsx(PhaseTimeline, { phases: d.phases }), tab === "Traces" && _jsx(OtelSpanTree, { spans: d.spans }), tab === "Ledger" && (_jsx("div", { className: "space-y-1 text-xs", children: w.actionLedger.map((a, i) => (_jsxs("div", { className: "panel panel-body", children: [_jsx("div", { className: "font-medium text-slate-800", children: a.action }), _jsxs("div", { className: "text-slate-500", children: [new Date(a.timestamp * 1000).toLocaleString(), " \u00B7 ", a.actorKind, ":", a.actorId, "\u00B7 ", a.revocable ? "revocable" : "non-revocable"] })] }, i))) })), tab === "Amplification" && _jsx(SkillAmplificationPanel, { items: d.amplifications }), tab === "Execution Timeline" &&
                        _jsx(ExecutionTimelineTab, { mcpCalls: d.mcpCalls, workflowId: w.id, onLogAction: logAction })] }), _jsxs("div", { className: "col-span-1 space-y-3", children: [_jsx(EconomicsPanel, { e: d.economics }), _jsx(FleetAssignment, { spans: d.spans }), _jsx(AuditTrail, { ledger: w.actionLedger })] })] }));
}

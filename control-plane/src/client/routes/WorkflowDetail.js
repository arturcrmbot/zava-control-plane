import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// src/client/routes/WorkflowDetail.tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import OtelSpanTree from "../components/OtelSpanTree";
import PhaseTimeline from "../components/PhaseTimeline";
import SkillAmplificationPanel from "../components/SkillAmplificationPanel";
const tabs = ["Overview", "Phases", "Traces", "Ledger", "Amplification"];
export default function WorkflowDetail() {
    const { id } = useParams();
    const [d, setD] = useState(null);
    const [tab, setTab] = useState("Overview");
    useEffect(() => {
        if (!id)
            return;
        void fetch(`/api/workflows/${id}`).then(r => r.json()).then(setD);
    }, [id]);
    if (!d)
        return _jsx("div", { className: "text-xs text-slate-500", children: "loading\u2026" });
    const w = d.workflow;
    return (_jsxs("div", { className: "space-y-3", children: [_jsxs("div", { children: [_jsxs("div", { className: "text-lg font-semibold", children: [w.id, " \u00B7 ", w.vendor.name] }), _jsxs("div", { className: "text-xs text-slate-400", children: [w.invoice.currency, " ", w.invoice.amount.toLocaleString(), " \u00B7 PO ", w.invoice.poRef, " \u00B7 ", w.agency] })] }), _jsx("div", { className: "flex gap-1 border-b border-slate-800", children: tabs.map(t => (_jsx("button", { onClick: () => setTab(t), className: `text-xs px-3 py-1.5 ${tab === t ? "text-slate-100 border-b-2 border-blue-400" : "text-slate-400"}`, children: t }, t))) }), tab === "Overview" && (_jsxs("div", { className: "text-xs text-slate-300 space-y-1", children: [_jsxs("div", { children: ["status: ", w.status] }), _jsxs("div", { children: ["phase: ", w.currentPhase] }), d.activeException && (_jsxs("div", { className: "mt-2 border border-amber-700 rounded p-2 bg-amber-950/30", children: [_jsxs("div", { className: "text-amber-300 font-medium", children: ["\u26A0 ", d.activeException.category, " \u00B7 ", d.activeException.severity] }), _jsx("div", { children: d.activeException.summary }), _jsxs("div", { className: "text-emerald-300", children: ["\u2192 ", d.activeException.recommendation] })] }))] })), tab === "Phases" && _jsx(PhaseTimeline, { phases: d.phases }), tab === "Traces" && _jsx(OtelSpanTree, { spans: d.spans }), tab === "Ledger" && (_jsx("div", { className: "space-y-1 text-xs", children: w.actionLedger.map((a, i) => (_jsxs("div", { className: "border border-slate-800 rounded p-2 bg-slate-900/30", children: [_jsx("div", { className: "text-slate-200", children: a.action }), _jsxs("div", { className: "text-slate-500", children: [new Date(a.timestamp).toLocaleString(), " \u00B7 ", a.actor.kind, ":", a.actor.id, " \u00B7 ", a.revocable ? "revocable" : "non-revocable"] })] }, i))) })), tab === "Amplification" && _jsx(SkillAmplificationPanel, { items: d.amplifications })] }));
}

import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// src/client/components/WhatIfPanel.tsx
import { useState } from "react";
export default function WhatIfPanel({ policyId }) {
    const [value, setValue] = useState("");
    const [result, setResult] = useState(null);
    const run = async () => {
        const r = await fetch("/api/policy/dry-run", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ policyId, proposedValue: Number(value), scopeDays: 7 })
        });
        setResult(await r.json());
    };
    const propose = async () => {
        await fetch("/api/policy/propose-change", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ policyId, proposedValue: Number(value), rationale: "Dry-run accepted", proposedBy: "finance-controller@wpp" })
        });
        alert("Change proposed. A PR has been opened for governance review.");
    };
    return (_jsxs("div", { className: "panel panel-body space-y-3", children: [_jsx("div", { className: "text-[11px] uppercase tracking-wide text-slate-500", children: "What-if analysis" }), _jsxs("div", { className: "flex gap-2 items-center", children: [_jsx("input", { value: value, onChange: e => setValue(e.target.value), placeholder: "proposed value", className: "bg-white border border-slate-300 rounded px-2 py-1 text-xs w-40 focus:outline-none focus:ring-2 focus:ring-blue-300" }), _jsx("button", { onClick: run, className: "btn-secondary text-xs py-1", children: "Run dry-run" })] }), result && (_jsxs("div", { className: "text-xs text-slate-700 space-y-1", children: [_jsxs("div", { children: ["Scope: last 7 days. Evaluated ", result.totalEvaluated, " workflows."] }), _jsxs("div", { className: "text-emerald-700 font-medium", children: [result.wouldBeDifferent, " would have decided differently."] }), result.impactedWorkflowIds.length > 0 && (_jsxs("div", { className: "text-slate-500", children: ["Impacted: ", result.impactedWorkflowIds.join(", ")] })), _jsx("button", { onClick: propose, className: "btn-primary text-xs mt-2 py-1", children: "Propose as change (opens PR)" })] }))] }));
}

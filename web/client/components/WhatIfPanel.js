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
    return (_jsxs("div", { className: "border border-slate-800 rounded p-3 bg-slate-900/30 space-y-2", children: [_jsx("div", { className: "text-xs uppercase text-slate-500", children: "What-if analysis" }), _jsxs("div", { className: "flex gap-2 items-center", children: [_jsx("input", { value: value, onChange: e => setValue(e.target.value), placeholder: "proposed value", className: "bg-slate-950 border border-slate-800 rounded px-2 py-1 text-xs w-40" }), _jsx("button", { onClick: run, className: "text-xs px-3 py-1.5 border border-slate-700 rounded hover:bg-slate-800", children: "Run dry-run" })] }), result && (_jsxs("div", { className: "text-xs text-slate-300 space-y-1", children: [_jsxs("div", { children: ["Scope: last 7 days. Evaluated ", result.totalEvaluated, " workflows."] }), _jsxs("div", { className: "text-emerald-300", children: [result.wouldBeDifferent, " would have decided differently."] }), result.impactedWorkflowIds.length > 0 && (_jsxs("div", { className: "text-slate-400", children: ["Impacted: ", result.impactedWorkflowIds.join(", ")] })), _jsx("button", { onClick: propose, className: "mt-2 text-xs px-3 py-1.5 bg-blue-600 rounded hover:bg-blue-500", children: "Propose as change (opens PR)" })] }))] }));
}

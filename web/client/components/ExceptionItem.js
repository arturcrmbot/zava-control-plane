import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
export default function ExceptionItem({ e, selected, onToggle, onResolved }) {
    const [open, setOpen] = useState(false);
    const [busy, setBusy] = useState(false);
    const resolveOne = async (action) => {
        setBusy(true);
        try {
            await fetch("/api/exceptions/bulk-resolve", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    exceptionIds: [e.id],
                    resolution: action,
                    resolvedBy: "finance-controller@wpp",
                }),
            });
            onResolved?.();
        }
        finally {
            setBusy(false);
        }
    };
    return (_jsxs("div", { className: "panel", children: [_jsxs("div", { className: "flex items-start gap-2 p-3", children: [_jsx("input", { type: "checkbox", className: "mt-1", checked: selected, onChange: () => onToggle(e.id) }), _jsxs("button", { onClick: () => setOpen(!open), className: "flex-1 text-left", children: [_jsxs("div", { className: "flex items-center gap-2 text-sm", children: [_jsx("span", { className: `px-1.5 py-0.5 rounded text-[10px] uppercase font-medium text-white ${e.severity === "critical" ? "bg-red-600" : e.severity === "high" ? "bg-orange-500" : "bg-amber-500"}`, children: e.severity }), _jsx("span", { className: "font-medium text-slate-800", children: e.category }), _jsxs("span", { className: "text-slate-500 text-xs", children: ["\u00B7 ", e.workflowId] }), e.bulkCandidateIds && e.bulkCandidateIds.length > 1 &&
                                        _jsxs("span", { className: "text-xs text-purple-700", children: ["bulk\u00D7", e.bulkCandidateIds.length] })] }), _jsx("div", { className: "text-xs text-slate-700 mt-1", children: e.summary }), _jsxs("div", { className: "text-[11px] text-emerald-700 mt-1", children: ["\u2192 ", e.recommendation] })] })] }), open && (_jsxs("div", { className: "px-4 pb-3 space-y-2 border-t border-slate-200", children: [e.relatedPolicyRefs.length > 0 && (_jsxs("div", { children: [_jsx("div", { className: "text-[11px] uppercase tracking-wide text-slate-500 mt-2", children: "Policy context" }), e.relatedPolicyRefs.map((p, i) => (_jsxs("div", { className: "text-xs text-slate-700 mt-1", children: [_jsx("div", { className: "font-medium text-slate-800", children: p.title }), _jsx("div", { className: "text-slate-500", children: p.snippet }), _jsx("div", { className: "text-[10px] text-slate-400", children: p.source })] }, i)))] })), _jsx("div", { className: "flex gap-2 pt-2 flex-wrap", children: e.options.map((o, i) => (_jsxs("button", { disabled: busy, onClick: () => resolveOne(o.action), "data-testid": `resolve-${o.action}`, className: "btn-secondary text-xs py-1 disabled:opacity-40", children: [o.label, o.nonRevocable ? " ⚠" : ""] }, i))) })] }))] }));
}

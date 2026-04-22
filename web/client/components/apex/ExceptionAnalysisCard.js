import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
function highlight(text) {
    // Highlight money amounts, GL codes, PO numbers, all-caps IDs.
    const parts = text.split(/(\b[A-Z]{2,}-[A-Z0-9-]+|\$?\d[\d,]*\.?\d*|\bGL-\d+)/);
    return parts.map((p, i) => (/^([A-Z]{2,}-[A-Z0-9-]+|\$?\d[\d,]*\.?\d*|GL-\d+)$/.test(p)
        ? _jsx("span", { className: "bg-amber-100 text-amber-900 rounded px-1", children: p }, i)
        : _jsx("span", { children: p }, i)));
}
export default function ExceptionAnalysisCard({ narrative }) {
    return (_jsxs("div", { className: "panel", "data-testid": "exception-analysis", children: [_jsxs("div", { className: "panel-header flex items-center gap-2", children: [_jsx("span", { className: "text-red-600", children: "\u26A0" }), _jsx("span", { children: "Exception Analysis" })] }), _jsxs("div", { className: "panel-body space-y-4 text-sm", children: [_jsxs("div", { children: [_jsx("div", { className: "text-[10px] uppercase tracking-wide text-slate-500 mb-1", children: "What Happened" }), _jsx("p", { className: "text-slate-800", children: highlight(narrative.whatHappened) })] }), _jsxs("div", { children: [_jsx("div", { className: "text-[10px] uppercase tracking-wide text-slate-500 mb-1", children: "What the Agent Tried" }), _jsx("ul", { className: "list-disc pl-5 space-y-1 text-slate-700", children: narrative.whatAgentTried.map((b, i) => _jsx("li", { children: b }, i)) })] }), _jsxs("div", { className: "bg-emerald-50 border border-emerald-200 rounded p-3", children: [_jsx("div", { className: "text-[10px] uppercase tracking-wide text-emerald-700 mb-1", children: "Agent Recommendation" }), _jsx("p", { className: "text-emerald-900", children: narrative.agentRecommendation })] })] })] }));
}

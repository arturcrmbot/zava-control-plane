import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// src/client/routes/Evaluations.tsx
import { useEffect, useState } from "react";
export default function Evaluations() {
    const [items, setItems] = useState([]);
    useEffect(() => {
        const tick = () => void fetch("/api/evals").then(r => r.json()).then(setItems);
        tick();
        const i = setInterval(tick, 5000);
        return () => clearInterval(i);
    }, []);
    const avg = (k) => items.length === 0 ? 0 : items.reduce((a, b) => a + b[k], 0) / items.length;
    return (_jsxs("div", { className: "space-y-4", children: [_jsxs("div", { children: [_jsx("div", { className: "text-lg font-semibold text-slate-900", children: "Continuous Evaluation" }), _jsxs("div", { className: "text-xs text-slate-500 mt-0.5", children: [items.length, " evals on sampled traces"] })] }), _jsxs("div", { className: "grid grid-cols-3 gap-3", children: [_jsx(Metric, { label: "Task adherence", v: avg("taskAdherence") }), _jsx(Metric, { label: "Safety", v: avg("safety") }), _jsx(Metric, { label: "Tool accuracy", v: avg("toolAccuracy") })] }), _jsxs("div", { className: "panel", children: [_jsx("div", { className: "panel-header", children: "Recent runs" }), _jsxs("div", { className: "divide-y divide-slate-200", children: [items.length === 0 && (_jsx("div", { className: "p-3 text-xs text-slate-500 italic", children: "No evaluation runs yet." })), items.slice(0, 20).map(e => (_jsxs("div", { className: "flex items-center gap-3 px-3 py-2 text-xs", children: [_jsx("a", { href: `/workflows/${e.workflowId}`, className: "text-blue-700 hover:underline font-mono", children: e.workflowId }), _jsx("span", { className: "text-slate-400", children: new Date(e.ranAt).toLocaleTimeString() }), _jsxs("span", { className: "ml-auto text-slate-600 font-mono", children: ["adh=", e.taskAdherence.toFixed(2), " \u00B7 safe=", e.safety.toFixed(2), " \u00B7 tool=", e.toolAccuracy.toFixed(2)] })] }, e.id)))] })] })] }));
}
function Metric({ label, v }) {
    return (_jsxs("div", { className: "panel panel-body", children: [_jsx("div", { className: "text-[11px] uppercase tracking-wide text-slate-500", children: label }), _jsxs("div", { className: "text-2xl font-semibold text-slate-900 mt-1", children: [(v * 100).toFixed(1), "%"] })] }));
}

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
    return (_jsxs("div", { className: "space-y-3", children: [_jsx("div", { className: "text-sm font-semibold", children: "Continuous Evaluation" }), _jsxs("div", { className: "text-xs text-slate-400", children: [items.length, " evals on sampled traces."] }), _jsxs("div", { className: "grid grid-cols-3 gap-3", children: [_jsx(Metric, { label: "Task adherence", v: avg("taskAdherence") }), _jsx(Metric, { label: "Safety", v: avg("safety") }), _jsx(Metric, { label: "Tool accuracy", v: avg("toolAccuracy") })] }), _jsx("div", { className: "space-y-1 text-xs", children: items.slice(0, 20).map(e => (_jsxs("div", { className: "border border-slate-800 rounded p-2 bg-slate-900/30", children: [_jsx("a", { href: `/workflows/${e.workflowId}`, className: "text-blue-300", children: e.workflowId }), _jsx("span", { className: "text-slate-500 ml-2", children: new Date(e.ranAt).toLocaleTimeString() }), _jsxs("span", { className: "ml-4 text-slate-400", children: ["adh=", e.taskAdherence.toFixed(2), " safe=", e.safety.toFixed(2), " tool=", e.toolAccuracy.toFixed(2)] })] }, e.id))) })] }));
}
function Metric({ label, v }) {
    return (_jsxs("div", { className: "border border-slate-800 rounded p-3 bg-slate-900/30", children: [_jsx("div", { className: "text-[11px] uppercase text-slate-500", children: label }), _jsxs("div", { className: "text-xl font-semibold", children: [(v * 100).toFixed(1), "%"] })] }));
}

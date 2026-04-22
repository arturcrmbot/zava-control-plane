import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// web/client/components/apex/FleetEconomicsPanel.tsx
import { useEffect, useState } from "react";
export default function FleetEconomicsPanel() {
    const [d, setD] = useState(null);
    useEffect(() => {
        const load = () => fetch("/api/fleet/economics").then(r => r.json()).then(setD);
        void load();
        const t = setInterval(load, 5000);
        return () => clearInterval(t);
    }, []);
    if (!d)
        return _jsx("div", { className: "panel panel-body text-xs text-slate-500", children: "loading economics\u2026" });
    return (_jsxs("div", { className: "panel", "data-testid": "fleet-economics", children: [_jsx("div", { className: "panel-header", children: "Fleet Economics" }), _jsxs("div", { className: "panel-body grid grid-cols-2 gap-2 text-sm", children: [_jsxs("div", { children: [_jsx("div", { className: "text-[10px] uppercase text-slate-500", children: "Compute (active)" }), _jsxs("div", { className: "font-semibold", children: ["$", d.totalComputeCostUsd.toFixed(2)] })] }), _jsxs("div", { children: [_jsx("div", { className: "text-[10px] uppercase text-slate-500", children: "Avg per wf" }), _jsxs("div", { className: "font-semibold", children: ["$", d.averageCostPerWorkflow.toFixed(2)] })] }), _jsxs("div", { children: [_jsx("div", { className: "text-[10px] uppercase text-slate-500", children: "Model calls" }), _jsx("div", { className: "font-semibold", children: d.totalModelCalls })] }), _jsxs("div", { children: [_jsx("div", { className: "text-[10px] uppercase text-slate-500", children: "Tool calls" }), _jsx("div", { className: "font-semibold", children: d.totalToolCalls })] })] })] }));
}

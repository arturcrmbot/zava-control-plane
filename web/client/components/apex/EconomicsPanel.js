import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export default function EconomicsPanel({ e }) {
    const tiles = [
        { k: "Compute cost", v: `$${e.computeCostUsd.toFixed(2)}` },
        { k: "Model calls", v: String(e.modelCalls) },
        { k: "Tool calls", v: String(e.toolCalls) },
        { k: "Days elapsed", v: String(e.daysElapsed.toFixed(1)) },
        { k: "SLA token", v: e.slaToken },
    ];
    return (_jsxs("div", { className: "panel", "data-testid": "economics-panel", children: [_jsx("div", { className: "panel-header", children: "Economics" }), _jsx("div", { className: "panel-body grid grid-cols-2 gap-2", children: tiles.map(t => (_jsxs("div", { className: "border border-slate-200 rounded p-2", children: [_jsx("div", { className: "text-[10px] uppercase tracking-wide text-slate-500", children: t.k }), _jsx("div", { className: "text-sm font-semibold text-slate-900", children: t.v })] }, t.k))) })] }));
}

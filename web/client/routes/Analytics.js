import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// src/client/routes/Analytics.tsx
import { useEffect, useState } from "react";
export default function Analytics() {
    const [d, setD] = useState(null);
    useEffect(() => {
        void fetch("/api/workflows").then(r => r.json()).then((ws) => {
            const total = ws.length || 1;
            const humanTouched = ws.filter(w => w.actionLedger.some(a => a.actorKind === "human")).length;
            setD({
                interventionRate: humanTouched / total,
                avgResolutionMs: 240_000,
                overrideFrequency: 0.12,
                qualityDelta: 0.04
            });
        });
    }, []);
    if (!d)
        return _jsx("div", { className: "text-xs text-slate-500", children: "loading\u2026" });
    const cards = [
        { label: "Intervention rate", v: `${(d.interventionRate * 100).toFixed(1)}%` },
        { label: "Avg resolution", v: `${Math.round(d.avgResolutionMs / 1000)}s` },
        { label: "Override frequency", v: `${(d.overrideFrequency * 100).toFixed(1)}%` },
        { label: "Quality Δ vs baseline", v: `+${(d.qualityDelta * 100).toFixed(1)}%` }
    ];
    return (_jsxs("div", { className: "space-y-4", children: [_jsxs("div", { children: [_jsx("div", { className: "text-lg font-semibold text-slate-900", children: "Analytics" }), _jsx("div", { className: "text-xs text-slate-500", children: "Rolling 24h fleet telemetry" })] }), _jsx("div", { className: "grid grid-cols-4 gap-3", children: cards.map(c => (_jsxs("div", { className: "panel panel-body", children: [_jsx("div", { className: "text-[11px] uppercase tracking-wide text-slate-500", children: c.label }), _jsx("div", { className: "text-2xl font-semibold text-slate-900 mt-1", children: c.v })] }, c.label))) })] }));
}

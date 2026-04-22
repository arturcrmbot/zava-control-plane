import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// web/client/components/apex/PolicyAutonomyPanel.tsx
import { useEffect, useState } from "react";
export default function PolicyAutonomyPanel() {
    const [items, setItems] = useState([]);
    useEffect(() => { void fetch("/api/policy/").then(r => r.json()).then(setItems); }, []);
    return (_jsxs("div", { className: "panel", "data-testid": "policy-autonomy", children: [_jsx("div", { className: "panel-header", children: "Policy & Autonomy" }), _jsxs("div", { className: "panel-body space-y-2", children: [items.length === 0 && _jsx("div", { className: "text-xs text-slate-500", children: "no policies loaded" }), items.map(p => {
                        const v = typeof p.currentValue === "number" ? p.currentValue :
                            typeof p.currentValue === "boolean" ? (p.currentValue ? 1 : 0) : 0.5;
                        const pct = Math.max(0, Math.min(1, v <= 1 ? v : v / 100));
                        return (_jsxs("div", { children: [_jsxs("div", { className: "flex justify-between text-xs", children: [_jsx("span", { className: "text-slate-700", children: p.description }), _jsx("span", { className: "text-slate-500", children: String(p.currentValue) })] }), _jsx("div", { className: "h-1.5 bg-slate-200 rounded mt-1", children: _jsx("div", { className: "h-1.5 bg-blue-500 rounded", style: { width: `${pct * 100}%` } }) })] }, p.id));
                    })] })] }));
}

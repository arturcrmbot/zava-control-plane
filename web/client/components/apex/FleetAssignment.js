import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export default function FleetAssignment({ spans }) {
    const byExecutor = new Map();
    for (const s of spans) {
        const name = String(s.attributes["executor.name"] ?? s.name);
        const type = String(s.attributes["executor.type"] ?? "unknown");
        const cur = byExecutor.get(name) ?? { type, status: "ok", count: 0 };
        cur.count += 1;
        if (s.status === "error")
            cur.status = "error";
        byExecutor.set(name, cur);
    }
    const rows = [...byExecutor.entries()];
    return (_jsxs("div", { className: "panel", "data-testid": "fleet-assignment", children: [_jsx("div", { className: "panel-header", children: "Fleet Assignment" }), _jsxs("div", { className: "panel-body space-y-1.5", children: [rows.length === 0 && _jsx("div", { className: "text-xs text-slate-500", children: "no executors fired yet" }), rows.map(([name, info]) => (_jsxs("div", { className: "flex items-center gap-2 text-sm min-w-0", children: [_jsx("span", { className: `shrink-0 w-2 h-2 rounded-full ${info.status === "error" ? "bg-red-500" : "bg-emerald-500"}` }), _jsx("span", { className: "text-slate-800 truncate flex-1 min-w-0", title: name, children: name }), _jsx("span", { className: "shrink-0 text-[10px] text-slate-500 uppercase tracking-wide", children: info.type.slice(0, 3) }), _jsxs("span", { className: "shrink-0 text-[11px] text-slate-500 tabular-nums", children: ["\u00D7", info.count] })] }, name)))] })] }));
}

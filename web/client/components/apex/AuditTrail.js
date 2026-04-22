import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export default function AuditTrail({ ledger }) {
    const last = ledger.slice(-8).reverse();
    return (_jsxs("div", { className: "panel", "data-testid": "audit-trail", children: [_jsxs("div", { className: "panel-header flex items-center justify-between", children: [_jsx("span", { children: "Audit Trail" }), _jsxs("span", { className: "text-[11px] font-normal text-slate-500", children: ["last ", last.length] })] }), _jsxs("div", { className: "panel-body space-y-1.5", children: [last.length === 0 && _jsx("div", { className: "text-xs text-slate-500", children: "no entries yet" }), last.map((e, i) => (_jsxs("div", { className: "text-xs", children: [_jsx("div", { className: "text-slate-800 font-medium", children: e.action }), _jsxs("div", { className: "text-slate-500", children: [new Date(e.timestamp * 1000).toLocaleString(), " \u00B7 ", e.actorKind, ":", e.actorId] })] }, i)))] })] }));
}

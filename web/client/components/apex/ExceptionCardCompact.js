import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// web/client/components/apex/ExceptionCardCompact.tsx
import { Link } from "react-router-dom";
export default function ExceptionCardCompact({ e }) {
    return (_jsxs(Link, { to: `/workflows/${e.workflowId}`, className: "panel block p-4 hover:border-blue-400 transition", children: [_jsxs("div", { className: "flex items-center gap-2 mb-2", children: [_jsx("span", { className: "chip-danger", children: e.severity }), _jsx("span", { className: "font-semibold text-slate-800", children: e.workflowId }), _jsxs("span", { className: "text-xs text-slate-500", children: ["\u00B7 ", e.category] })] }), _jsx("div", { className: "text-sm text-slate-700 line-clamp-2", children: e.summary }), _jsxs("div", { className: "text-xs text-emerald-700 mt-2", children: ["\u2192 ", e.recommendation] })] }));
}

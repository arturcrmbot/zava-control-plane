import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export default function SkillAmplificationPanel({ items }) {
    if (items.length === 0)
        return _jsx("div", { className: "text-xs text-slate-500", children: "No skill amplification for this workflow yet." });
    return (_jsx("div", { className: "space-y-2", children: items.map(a => (_jsxs("div", { className: "panel panel-body text-xs space-y-2", children: [_jsxs("div", { className: "text-emerald-700 font-medium", children: ["\u2192 ", a.recommendedApproach] }), a.policyContext.map((p, i) => (_jsxs("div", { children: [_jsx("div", { className: "font-medium text-slate-800", children: p.title }), _jsx("div", { className: "text-slate-500", children: p.snippet })] }, i))), a.precedents.length > 0 && (_jsxs("div", { children: [_jsx("div", { className: "text-[10px] uppercase tracking-wide text-slate-500", children: "Precedents" }), a.precedents.map((p, i) => (_jsxs("div", { className: "text-slate-600", children: ["\u00B7 ", p.workflowId, " \u2192 ", p.outcome, ": ", p.rationale] }, i)))] }))] }, a.id))) }));
}

import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export default function SkillAmplificationPanel({ items }) {
    if (items.length === 0)
        return _jsx("div", { className: "text-xs text-slate-500", children: "No skill amplification for this workflow yet." });
    return (_jsx("div", { className: "space-y-2", children: items.map(a => (_jsxs("div", { className: "border border-slate-800 rounded p-2 bg-slate-900/30 text-xs", children: [_jsxs("div", { className: "text-emerald-300 font-medium", children: ["\u2192 ", a.recommendedApproach] }), a.policyContext.map((p, i) => (_jsxs("div", { className: "mt-1", children: [_jsx("div", { className: "font-medium text-slate-200", children: p.title }), _jsx("div", { className: "text-slate-400", children: p.snippet })] }, i))), a.precedents.length > 0 && (_jsxs("div", { className: "mt-1", children: [_jsx("div", { className: "text-[10px] uppercase text-slate-500", children: "Precedents" }), a.precedents.map((p, i) => (_jsxs("div", { className: "text-slate-400", children: ["\u00B7 ", p.workflowId, " \u2192 ", p.outcome, ": ", p.rationale] }, i)))] }))] }, a.id))) }));
}

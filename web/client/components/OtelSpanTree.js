import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export default function OtelSpanTree({ spans }) {
    const sorted = [...spans].sort((a, b) => a.startMs - b.startMs);
    return (_jsx("div", { className: "space-y-1.5 font-mono text-xs", children: sorted.map(s => (_jsxs("div", { className: "bg-white border border-slate-200 rounded px-3 py-2", children: [_jsxs("div", { className: "flex justify-between", children: [_jsx("span", { className: "text-slate-800 font-medium", children: s.name }), _jsxs("span", { className: "text-slate-500", children: [Math.round(s.endMs - s.startMs), " ms"] })] }), _jsxs("div", { className: "text-[10px] text-slate-500 mt-0.5", children: ["phase=", s.attributes["workflow.phase"], s.attributes["tool.name"] ? ` · tool=${s.attributes["tool.name"]}` : "", s.attributes["llm.model"] ? ` · model=${s.attributes["llm.model"]}` : "", s.attributes["cost.usd"] != null ? ` · $${s.attributes["cost.usd"].toFixed(4)}` : ""] })] }, s.spanId))) }));
}

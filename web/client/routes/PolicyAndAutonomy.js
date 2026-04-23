import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// src/client/routes/PolicyAndAutonomy.tsx
import { useEffect, useState } from "react";
import WhatIfPanel from "../components/WhatIfPanel";
export default function PolicyAndAutonomy() {
    const [policies, setPolicies] = useState([]);
    const [selected, setSelected] = useState(null);
    useEffect(() => {
        void fetch("/api/policy").then(r => r.json()).then((ps) => {
            setPolicies(ps);
            if (ps[0])
                setSelected(ps[0].id);
        });
    }, []);
    return (_jsxs("div", { className: "space-y-4", children: [_jsxs("div", { children: [_jsx("div", { className: "text-lg font-semibold text-slate-900", children: "Policy & Autonomy" }), _jsxs("div", { className: "text-xs text-slate-500 mt-1 max-w-3xl", children: ["Autonomy policy is declarative and version-controlled. This screen is ", _jsx("em", { children: "read-first" }), ". Proposals go through a change-request flow \u2014 the Control Plane never mutates live governance."] })] }), _jsxs("div", { className: "grid grid-cols-2 gap-3", children: [_jsx("div", { className: "space-y-2", children: policies.map(p => (_jsxs("button", { onClick: () => setSelected(p.id), className: `w-full text-left panel panel-body transition ${selected === p.id ? "ring-2 ring-blue-500" : "hover:border-slate-300"}`, children: [_jsx("div", { className: "text-sm font-medium text-slate-800", children: p.id }), _jsx("div", { className: "text-xs text-slate-500 mt-0.5", children: p.description }), _jsxs("div", { className: "text-xs mt-2 text-slate-600", children: ["current: ", _jsx("span", { className: "text-slate-900 font-medium", children: String(p.currentValue) })] }), _jsxs("div", { className: "text-[10px] text-slate-400 mt-1", children: ["sha:", p.gitSha, " \u00B7 ", p.author, " \u00B7 ", new Date(p.updatedAt).toISOString().slice(0, 10)] })] }, p.id))) }), _jsx("div", { children: selected && _jsx(WhatIfPanel, { policyId: selected }) })] })] }));
}

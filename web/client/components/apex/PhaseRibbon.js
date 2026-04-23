import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { PHASE_ORDER } from "@shared/types";
import { Check, Loader2, Ban, CircleDashed } from "lucide-react";
function classify(name, phases, currentPhase, hasException) {
    const p = phases.find(x => x.name === name);
    if (p?.status === "completed")
        return "completed";
    if (name === currentPhase && hasException)
        return "blocked";
    if (name === currentPhase)
        return "in_progress";
    return "pending";
}
const Icon = ({ s }) => {
    if (s === "completed")
        return _jsx(Check, { size: 14, className: "text-emerald-600" });
    if (s === "in_progress")
        return _jsx(Loader2, { size: 14, className: "text-blue-600 animate-spin" });
    if (s === "blocked")
        return _jsx(Ban, { size: 14, className: "text-red-600" });
    return _jsx(CircleDashed, { size: 14, className: "text-slate-400" });
};
const PILL = {
    completed: "bg-emerald-50 border-emerald-200 text-emerald-800",
    in_progress: "bg-blue-50 border-blue-200 text-blue-800",
    blocked: "bg-red-50 border-red-200 text-red-800",
    pending: "bg-slate-50 border-slate-200 text-slate-500",
};
export default function PhaseRibbon({ workflow, phases }) {
    const hasException = !!workflow.activeExceptionId;
    return (_jsx("div", { className: "flex flex-wrap items-center gap-y-2 gap-x-1.5", "data-testid": "phase-ribbon", children: PHASE_ORDER.map((name, i) => {
            const s = classify(name, phases, workflow.currentPhase, hasException);
            return (_jsxs("div", { className: "flex items-center gap-1.5", children: [_jsxs("div", { className: `flex items-center gap-1.5 rounded-full px-2.5 py-1 border ${PILL[s]}`, children: [_jsx(Icon, { s: s }), _jsx("span", { className: "text-xs font-medium whitespace-nowrap", children: name })] }), i < PHASE_ORDER.length - 1 &&
                        _jsx("div", { className: "h-px w-3 bg-slate-300" })] }, name));
        }) }));
}

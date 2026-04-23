import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// src/client/components/OrchestrationView.tsx
import { useEffect, useState } from "react";
const stepNames = ["Intake", "Validation", "Routing", "Approval", "Payment", "Reconciliation"];
const exTypeLabel = (t) => {
    if (t === "agent")
        return _jsx("span", { className: "text-purple-700 font-mono text-[10px]", children: "[agt]" });
    if (t === "validator")
        return _jsx("span", { className: "text-amber-700 font-mono text-[10px]", children: "[val]" });
    if (t === "deterministic")
        return _jsx("span", { className: "text-slate-500 font-mono text-[10px]", children: "[det]" });
    return _jsx("span", { className: "text-slate-400 font-mono text-[10px]", children: "[ ?]" });
};
function deriveStepView(history, name) {
    const stepStart = history.find(h => h.kind === "step.started" && h.payload.step === name);
    const stepEnd = history.find(h => h.kind === "step.completed" && h.payload.step === name);
    const stepFailed = history.find(h => h.kind === "step.failed" && h.payload.step === name);
    const stepStartIdx = stepStart ? history.indexOf(stepStart) : -1;
    const stepEndIdx = stepEnd ? history.indexOf(stepEnd) : (stepFailed ? history.indexOf(stepFailed) : history.length);
    // Suspended/resumed events are siblings of the Approval step (no step name in payload — use ordering)
    const inWindow = (_h, idx) => idx > stepStartIdx && idx <= stepEndIdx;
    let suspended;
    let resumed;
    let blocked;
    let rejected;
    const executors = [];
    history.forEach((h, idx) => {
        if (!stepStart || !inWindow(h, idx))
            return;
        if (h.kind === "executor.invoked" && h.payload.stage === "complete")
            executors.push(h);
        if (h.kind === "validator.blocked")
            blocked = h;
        if (h.kind === "suspended" && name === "Approval")
            suspended = h;
        if (h.kind === "resumed" && name === "Approval")
            resumed = h;
        if (h.kind === "workflow.rejected" && name === "Approval")
            rejected = h;
    });
    return {
        name: name,
        started: stepStart, completed: stepEnd, failed: stepFailed,
        suspended, resumed, rejected, executors, blocked,
    };
}
export default function OrchestrationView({ workflowId }) {
    const [data, setData] = useState(null);
    useEffect(() => {
        const tick = () => void fetch(`/api/workflows/${workflowId}/orchestration`)
            .then(r => r.ok ? r.json() : null)
            .then(setData);
        tick();
        const i = setInterval(tick, 1500);
        return () => clearInterval(i);
    }, [workflowId]);
    if (!data)
        return _jsx("div", { className: "text-xs text-slate-500", children: "loading orchestration\u2026" });
    const stepViews = stepNames.map(name => deriveStepView(data.history, name));
    return (_jsxs("div", { className: "space-y-3 text-xs", children: [_jsxs("div", { className: "panel panel-body space-y-0.5", children: [_jsxs("div", { className: "text-slate-700", children: ["Durable Workflow: ", _jsx("span", { className: "text-slate-900 font-medium", children: "InvoiceP2POrchestrator" })] }), _jsxs("div", { className: "text-slate-700", children: ["instance: ", _jsx("span", { className: "text-slate-600 font-mono", children: data.instance_id || "—" })] }), _jsxs("div", { className: "text-slate-700", children: ["status: ", _jsx("span", { className: "text-slate-900 font-medium", children: data.status })] })] }), _jsx("div", { className: "space-y-2", children: stepViews.map(s => (_jsxs("div", { className: "panel", children: [_jsxs("div", { className: "px-3 py-2 flex items-center gap-2", children: [_jsx("div", { className: "w-32 text-slate-800 font-medium", children: s.name }), s.rejected ? _jsx("div", { className: "text-red-700", children: "\u2717 rejected" })
                                    : s.failed ? _jsx("div", { className: "text-red-700", children: "\u2717 failed" })
                                        : s.completed ? _jsx("div", { className: "text-emerald-700", children: "\u2713 completed" })
                                            : s.suspended && !s.resumed ? _jsx("div", { className: "text-amber-700", children: "\u23F8 suspended" })
                                                : s.blocked ? _jsx("div", { className: "text-red-700", children: "\u2717 blocked" })
                                                    : s.started ? _jsx("div", { className: "text-blue-700", children: "running" })
                                                        : _jsx("div", { className: "text-slate-400", children: "not started" }), s.completed?.payload?.duration_ms != null && (_jsxs("div", { className: "text-slate-500 ml-auto", children: [s.completed.payload.duration_ms, " ms"] }))] }), (s.executors.length > 0 || s.blocked || s.suspended || s.rejected) && (_jsxs("div", { className: "border-t border-slate-200 px-3 py-2 space-y-0.5 bg-slate-50", children: [s.executors.map((e, i) => (_jsxs("div", { className: "flex items-center gap-2 text-[11px]", children: [exTypeLabel(e.payload.type), _jsx("span", { className: "text-slate-700 font-mono", children: e.payload.name }), _jsxs("span", { className: "text-slate-500 ml-auto", children: [e.payload.duration_ms, " ms"] })] }, i))), s.blocked && (_jsxs("div", { className: "text-red-700 mt-1", children: ["\u21B3 ", String(s.blocked.payload.name ?? ""), " blocked: ", String(s.blocked.payload.reason ?? ""), " \u2192 routed to Fleet Manager"] })), s.suspended && !s.resumed && (_jsx("div", { className: "text-amber-700 mt-1", children: "\u21B3 awaiting `approval_decision` (zero compute)" })), s.resumed && (_jsx("div", { className: "text-emerald-700 mt-1", children: "\u21B3 resumed with operator decision" })), s.rejected && (_jsxs("div", { className: "text-red-700 mt-1", children: ["\u21B3 rejected by ", String(s.rejected.payload.by ?? "operator"), s.rejected.payload.reason ? ` (${String(s.rejected.payload.reason)})` : ""] })), s.failed?.payload?.error && (_jsxs("div", { className: "text-red-700 mt-1", children: ["\u21B3 error: ", String(s.failed.payload.error)] }))] }))] }, s.name))) })] }));
}

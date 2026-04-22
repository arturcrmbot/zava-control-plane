import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// web/client/components/apex/InterventionProtocols.tsx
import { useState } from "react";
export default function InterventionProtocols({ exception, onResolved }) {
    const [busy, setBusy] = useState(false);
    const act = async (action) => {
        setBusy(true);
        try {
            await fetch("/api/exceptions/bulk-resolve", {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    exceptionIds: [exception.id],
                    resolution: action,
                    resolvedBy: "finance-controller@wpp",
                }),
            });
            onResolved?.();
        }
        finally {
            setBusy(false);
        }
    };
    return (_jsxs("div", { className: "panel", "data-testid": "intervention-protocols", children: [_jsx("div", { className: "panel-header", children: "Intervention Protocols" }), _jsx("div", { className: "panel-body grid grid-cols-2 gap-2", children: exception.options.map(o => (_jsxs("button", { disabled: busy, onClick: () => act(o.action), "data-testid": `protocol-${o.action}`, className: o.recommended ? "btn-primary" :
                        o.action === "reject" ? "btn-danger" : "btn-secondary", children: [o.recommended && _jsx("span", { className: "text-[10px] uppercase tracking-wider bg-white/20 rounded px-1", children: "recommended" }), o.label, o.nonRevocable ? " ⚠" : ""] }, o.action))) })] }));
}

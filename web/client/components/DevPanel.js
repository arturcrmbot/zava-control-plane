import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// src/client/components/DevPanel.tsx
// Dev-only scenario injector. Hidden in production builds via import.meta.env.DEV.
// Posts to /api/simulator/inject to fire the three demo paths plus a Reset hint
// for Azurite (handled out-of-band by the Makefile — spec forbids a new server route).
/// <reference types="vite/client" />
import { useState } from "react";
export default function DevPanel() {
    if (!import.meta.env.DEV)
        return null;
    return _jsx(DevPanelInner, {});
}
function DevPanelInner() {
    const [open, setOpen] = useState(false);
    const [busy, setBusy] = useState(null);
    const [last, setLast] = useState(null);
    const inject = async (scenario) => {
        setBusy(scenario);
        setLast(null);
        try {
            const body = scenario === "normal" ? {} : { scenario };
            const r = await fetch("/api/simulator/inject", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            const j = (await r.json());
            setLast(j.workflow_id ? `injected ${scenario}: ${j.workflow_id}` : `injected ${scenario}`);
        }
        catch (ex) {
            setLast(`error: ${ex instanceof Error ? ex.message : String(ex)}`);
        }
        finally {
            setBusy(null);
        }
    };
    return (_jsxs("div", { className: "fixed top-2 right-2 z-40 text-xs", children: [_jsxs("button", { onClick: () => setOpen(o => !o), className: "px-2 py-1 border border-amber-700 bg-amber-900/30 text-amber-300 rounded hover:bg-amber-900/60", title: "Dev tools \u2014 hidden in production builds", children: ["Dev ", open ? "v" : ">"] }), open && (_jsxs("div", { className: "mt-1 w-72 border border-slate-700 bg-slate-900 rounded p-3 space-y-2 shadow-lg", children: [_jsx("div", { className: "font-semibold text-slate-200", children: "Inject scenario" }), _jsxs("div", { className: "flex flex-col gap-1", children: [_jsx("button", { onClick: () => void inject("normal"), disabled: busy !== null, className: "px-2 py-1 border border-slate-700 rounded hover:bg-slate-800 disabled:opacity-50 text-left", children: "Inject normal" }), _jsx("button", { onClick: () => void inject("demo-fail"), disabled: busy !== null, className: "px-2 py-1 border border-red-700 bg-red-900/20 text-red-300 rounded hover:bg-red-900/40 disabled:opacity-50 text-left", children: "Inject demo-fail (validator blocks at Routing)" }), _jsx("button", { onClick: () => void inject("demo-hitl"), disabled: busy !== null, className: "px-2 py-1 border border-amber-700 bg-amber-900/20 text-amber-300 rounded hover:bg-amber-900/40 disabled:opacity-50 text-left", children: "Inject demo-hitl (Approval suspends)" })] }), _jsxs("div", { className: "pt-1 border-t border-slate-800", children: [_jsx("div", { className: "font-semibold text-slate-200 mb-1", children: "Reset Azurite" }), _jsxs("div", { className: "text-[11px] text-slate-400 leading-snug", children: ["Use the Makefile:", _jsx("pre", { className: "mt-1 px-2 py-1 bg-slate-950 border border-slate-800 rounded text-slate-300", children: "make reset-azurite" })] })] }), last && _jsx("div", { className: "text-[11px] text-slate-400 break-all", children: last })] }))] }));
}

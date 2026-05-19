// src/client/components/DevPanel.tsx
// Dev-only scenario injector. Hidden in production builds via import.meta.env.DEV.
// Posts to /api/simulator/inject to fire the three demo paths plus a Reset hint
// for Azurite (handled out-of-band by the Makefile — spec forbids a new server route).
/// <reference types="vite/client" />
import { useState } from "react";

type Scenario = "normal" | "demo-fail" | "demo-hitl";

export default function DevPanel() {
  if (!import.meta.env.DEV) return null;
  return <DevPanelInner />;
}

function DevPanelInner() {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<Scenario | null>(null);
  const [last, setLast] = useState<string | null>(null);

  const inject = async (scenario: Scenario) => {
    setBusy(scenario);
    setLast(null);
    try {
      const body = scenario === "normal" ? {} : { scenario };
      const r = await fetch("/api/simulator/inject", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const j = (await r.json()) as { workflow_id?: string };
      setLast(j.workflow_id ? `injected ${scenario}: ${j.workflow_id}` : `injected ${scenario}`);
    } catch (ex) {
      setLast(`error: ${ex instanceof Error ? ex.message : String(ex)}`);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="fixed top-2 right-2 z-40 text-xs">
      <button
        onClick={() => setOpen(o => !o)}
        className="px-2 py-1 border border-amber-300 bg-amber-50 dark:bg-amber-950/30 text-amber-800 rounded hover:bg-amber-100 font-medium"
        title="Dev tools — hidden in production builds"
      >
        Dev {open ? "▾" : "▸"}
      </button>
      {open && (
        <div className="mt-1 w-72 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg p-3 space-y-2 shadow-xl">
          <div className="font-semibold text-slate-800 dark:text-slate-100">Inject scenario</div>
          <div className="flex flex-col gap-1">
            <button
              onClick={() => void inject("normal")}
              disabled={busy !== null}
              className="px-2 py-1 border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-200 rounded hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50 text-left"
            >
              Inject normal
            </button>
            <button
              onClick={() => void inject("demo-fail")}
              disabled={busy !== null}
              className="px-2 py-1 border border-red-300 bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-400 rounded hover:bg-red-100 disabled:opacity-50 text-left"
            >
              Inject demo-fail (validator blocks at Routing)
            </button>
            <button
              onClick={() => void inject("demo-hitl")}
              disabled={busy !== null}
              className="px-2 py-1 border border-amber-300 bg-amber-50 dark:bg-amber-950/30 text-amber-800 rounded hover:bg-amber-100 disabled:opacity-50 text-left"
            >
              Inject demo-hitl (Approval suspends)
            </button>
          </div>
          <div className="pt-2 border-t border-slate-200 dark:border-slate-700">
            <div className="font-semibold text-slate-800 dark:text-slate-100 mb-1">Reset Azurite</div>
            <div className="text-[11px] text-slate-500 dark:text-slate-400 leading-snug">
              Use the Makefile:
              <pre className="mt-1 px-2 py-1 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded text-slate-700 dark:text-slate-200">make reset-azurite</pre>
            </div>
          </div>
          {last && <div className="text-[11px] text-slate-600 dark:text-slate-300 break-all">{last}</div>}
        </div>
      )}
    </div>
  );
}

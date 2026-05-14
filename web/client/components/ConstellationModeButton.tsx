// Constellation Mode button.
//
// Always visible (unlike DevPanel which is dev-only). Clicking POSTs to
// /api/simulator/constellation-start. Server-side that endpoint flips
// PERSONA_AUTO_CLOSE on at runtime AND spawns one workflow per known
// domain so the constellation view fills instantly.
//
// The button is the on-screen replacement for `source scripts/profile-
// everything.sh && make up` so the operator does not have to leave the
// browser to run the autonomous-org finale.
import { useState } from "react";

type SpawnRow = { domain: string; workflow_id: string };
type FailRow = { domain: string; error: string };

type ConstellationResult = {
  ok: boolean;
  auto_close_count: number;
  spawned: SpawnRow[];
  failed: FailRow[];
};

export default function ConstellationModeButton() {
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [result, setResult] = useState<ConstellationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onClick = async () => {
    if (!confirming) {
      // Two-click confirm so a stray click during the demo does not
      // accidentally swap the substrate to fully autonomous mid-walkthrough.
      setConfirming(true);
      window.setTimeout(() => setConfirming(false), 4000);
      return;
    }
    setConfirming(false);
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await fetch("/api/simulator/constellation-start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      if (!r.ok) {
        throw new Error(`HTTP ${r.status}`);
      }
      const j = (await r.json()) as ConstellationResult;
      setResult(j);
    } catch (ex) {
      setError(ex instanceof Error ? ex.message : String(ex));
    } finally {
      setBusy(false);
    }
  };

  const label = busy
    ? "Activating…"
    : confirming
    ? "Click again to confirm"
    : "🌌 Constellation Mode";

  return (
    <div className="flex flex-col items-end gap-1 text-xs">
      <button
        type="button"
        onClick={() => void onClick()}
        disabled={busy}
        title="Switch the substrate to autonomous-org mode: every persona auto-closes its gate, and one workflow is spawned in every domain right now so the constellation view fills."
        className={`px-3 py-1.5 rounded font-medium transition-colors border ${
          confirming
            ? "bg-amber-500 text-white border-amber-600 hover:bg-amber-600"
            : "bg-indigo-600 text-white border-indigo-700 hover:bg-indigo-700"
        } disabled:opacity-50`}
      >
        {label}
      </button>
      {result && (
        <div className="text-[11px] text-slate-600 max-w-xs text-right">
          spawned <strong>{result.spawned.length}</strong> domains; auto-close
          {" "}<strong>{result.auto_close_count}</strong> personae
          {result.failed.length > 0 && (
            <span className="text-red-700">
              {" "}· {result.failed.length} failed
            </span>
          )}
        </div>
      )}
      {error && (
        <div className="text-[11px] text-red-700 max-w-xs text-right">
          error: {error}
        </div>
      )}
    </div>
  );
}

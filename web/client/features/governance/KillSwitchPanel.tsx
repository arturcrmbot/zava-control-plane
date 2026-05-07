// web/client/features/governance/KillSwitchPanel.tsx
//
// Phase 7 TASK-054 of plan/feature-agent-governance-toolkit-1.md.
//
// Operator surface: pause an agent or block a tool fleet-wide for a TTL,
// no redeploy. Sub-second to flip; the kernel consults the kill table
// on every evaluate_tool_call (TASK-052).
//
// Slotted into WorkflowDetail's sidebar. Lists currently-active kills
// with countdown timers + remove buttons; a small form lets the operator
// post a new kill (defaults to a 30-minute TTL — change to taste).
//
// No new top-level navigation (CON-004). Auth lives at the route layer
// (api/server/routes/governance.py — currently open in the lab path,
// engagement-POC slots a Bearer check there).
import { useEffect, useRef, useState } from "react";

type Kill = {
  kill_id: string;
  actor: string;
  tool: string;
  created_at: number;
  expires_at: number;
  reason: string;
  created_by: string;
};

type KillsResponse = { kills: Kill[]; total: number };

const REFRESH_MS = 5_000;

function fmtRemaining(seconds: number): string {
  if (seconds <= 0) return "expired";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${(seconds / 3600).toFixed(1)}h`;
}

export default function KillSwitchPanel() {
  const [kills, setKills] = useState<Kill[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [actor, setActor] = useState("*");
  const [tool, setTool] = useState("*");
  const [ttlMinutes, setTtlMinutes] = useState(30);
  const [reason, setReason] = useState("");
  const [now, setNow] = useState(Date.now() / 1000);
  const tickRef = useRef<number | null>(null);

  async function refresh() {
    if (typeof fetch !== "function") return;  // jsdom / SSR safety
    try {
      const r = await fetch("/api/governance/kill");
      if (!r.ok) {
        setError(`HTTP ${r.status}`);
        return;
      }
      const body: KillsResponse = await r.json();
      setKills(body.kills ?? []);
      setError(null);
    } catch (ex) {
      setError(String(ex));
    }
  }

  useEffect(() => {
    refresh();
    const iv = window.setInterval(refresh, REFRESH_MS);
    return () => window.clearInterval(iv);
  }, []);

  // Light tick so countdowns visibly update between fetches.
  useEffect(() => {
    tickRef.current = window.setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => {
      if (tickRef.current !== null) window.clearInterval(tickRef.current);
    };
  }, []);

  async function add() {
    if (!reason.trim()) {
      setError("reason is required");
      return;
    }
    setBusy(true);
    try {
      const r = await fetch("/api/governance/kill", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          actor: actor.trim() || "*",
          tool: tool.trim() || "*",
          ttl_seconds: Math.max(1, Math.round(ttlMinutes * 60)),
          reason: reason.trim(),
        }),
      });
      if (!r.ok) {
        setError(`HTTP ${r.status}`);
      } else {
        setReason("");
        await refresh();
      }
    } catch (ex) {
      setError(String(ex));
    } finally {
      setBusy(false);
    }
  }

  async function remove(kill_id: string) {
    setBusy(true);
    try {
      const r = await fetch(`/api/governance/kill/${encodeURIComponent(kill_id)}`, {
        method: "DELETE",
      });
      if (!r.ok && r.status !== 404) {
        setError(`HTTP ${r.status}`);
      }
      await refresh();
    } catch (ex) {
      setError(String(ex));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-md border border-zinc-200 bg-white p-3">
      <div className="mb-2 flex items-baseline justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-700">
          Kill switches
        </h3>
        <span className="text-xs text-zinc-500">{kills.length} active</span>
      </div>

      {error && (
        <div className="mb-2 rounded border border-rose-200 bg-rose-50 px-2 py-1 text-xs text-rose-700">
          {error}
        </div>
      )}

      {/* Active list */}
      {kills.length > 0 && (
        <ul className="mb-3 space-y-1">
          {kills.map((k) => (
            <li
              key={k.kill_id}
              className="flex items-center justify-between rounded border border-rose-200 bg-rose-50 px-2 py-1 text-xs"
            >
              <div className="min-w-0 flex-1">
                <div className="truncate font-mono text-rose-800">
                  {k.actor} → {k.tool}
                </div>
                <div className="truncate text-rose-700">{k.reason}</div>
              </div>
              <div className="ml-2 flex items-center gap-1">
                <span className="font-mono text-rose-700">
                  {fmtRemaining(k.expires_at - now)}
                </span>
                <button
                  type="button"
                  onClick={() => remove(k.kill_id)}
                  disabled={busy}
                  className="rounded border border-rose-300 bg-white px-1.5 py-0.5 text-[11px] text-rose-700 hover:bg-rose-100 disabled:opacity-50"
                  title="Remove kill"
                >
                  ✕
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* Add form */}
      <details className="text-xs">
        <summary className="cursor-pointer text-zinc-600 hover:text-zinc-900">
          Add a kill
        </summary>
        <div className="mt-2 space-y-2">
          <label className="block">
            <span className="text-[11px] uppercase tracking-wide text-zinc-500">
              actor (or *)
            </span>
            <input
              className="mt-0.5 w-full rounded border border-zinc-300 px-2 py-1 font-mono text-xs"
              value={actor}
              onChange={(e) => setActor(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-[11px] uppercase tracking-wide text-zinc-500">
              tool (or *)
            </span>
            <input
              className="mt-0.5 w-full rounded border border-zinc-300 px-2 py-1 font-mono text-xs"
              value={tool}
              onChange={(e) => setTool(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-[11px] uppercase tracking-wide text-zinc-500">
              ttl (minutes)
            </span>
            <input
              type="number"
              min={1}
              className="mt-0.5 w-full rounded border border-zinc-300 px-2 py-1 font-mono text-xs"
              value={ttlMinutes}
              onChange={(e) => setTtlMinutes(parseInt(e.target.value, 10) || 1)}
            />
          </label>
          <label className="block">
            <span className="text-[11px] uppercase tracking-wide text-zinc-500">
              reason
            </span>
            <input
              className="mt-0.5 w-full rounded border border-zinc-300 px-2 py-1 text-xs"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. anomalous spike on this tool"
            />
          </label>
          <button
            type="button"
            onClick={add}
            disabled={busy || !reason.trim()}
            className="w-full rounded bg-rose-600 px-2 py-1 text-xs font-medium text-white hover:bg-rose-700 disabled:opacity-50"
          >
            {busy ? "…" : "Add kill"}
          </button>
          <p className="text-[10px] leading-snug text-zinc-500">
            Use <span className="font-mono">*</span> as a wildcard. The
            kernel consults this list on every MCP call. Lazy expiry.
          </p>
        </div>
      </details>
    </div>
  );
}

import { useEffect, useState } from "react";

/**
 * WorldSignalsPanel — live readout of the world-simulator engine on the cosmic
 * lens. Polls GET /api/world/state (~1s, matching the engine tick) and renders
 * the living world: support backlog, agent capacity, SLA-breach %, arrival
 * rate, and the last Durable responder decision (hired N + real instance id).
 *
 * Self-contained: no shared-stream plumbing. Renders nothing when the engine is
 * off (ZAVA_WORLD unset -> {enabled:false}), so it never disturbs the normal
 * lens. Backend already exposes everything this needs — see
 * api/server/routes/world.py.
 */
interface WorldState {
  enabled: boolean;
  pack?: string;
  stocks?: Record<string, number>;
  resources?: Record<string, number>;
  signals?: Record<string, number>;
  inputs?: Record<string, number>;
  last_response?: { instance_id?: string; hired?: number } | null;
}

export function WorldSignalsPanel() {
  const [state, setState] = useState<WorldState | null>(null);

  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const r = await fetch("/api/world/state");
        const d = (await r.json()) as WorldState;
        if (alive) setState(d);
      } catch {
        /* transient — keep last state */
      }
    };
    poll();
    const id = setInterval(poll, 1000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  if (!state || !state.enabled) return null;

  const backlog = state.stocks?.support_backlog ?? 0;
  const agents = state.resources?.agents ?? 0;
  const breach = state.signals?.sla_breach_pct ?? 0;
  const arrival = state.inputs?.ticket_arrival_rate ?? 0;
  const lr = state.last_response;
  const breachHot = breach > 0.5;

  return (
    <div
      data-testid="world-signals-panel"
      style={{
        position: "absolute",
        top: 180,
        left: 16,
        zIndex: 25,
        pointerEvents: "none",
        background: "rgba(2,6,23,0.82)",
        border: "1px solid rgba(56,189,248,0.28)",
        padding: "10px 12px",
        minWidth: 300,
        fontFamily: "ui-monospace, SFMono-Regular, 'Roboto Mono', monospace",
        backdropFilter: "blur(8px)",
      }}
    >
      <div
        style={{
          fontSize: 9,
          textTransform: "uppercase",
          letterSpacing: 1.2,
          color: "#38bdf8",
          marginBottom: 8,
        }}
      >
        World Simulator · {state.pack}
      </div>
      <div style={{ display: "flex", gap: 10 }}>
        <Stat title="Backlog" value={Math.round(backlog)} />
        <Stat title="Agents" value={Math.round(agents)} />
        <Stat title="SLA breach" value={`${(breach * 100).toFixed(0)}%`} hot={breachHot} />
        <Stat title="Arrivals/h" value={Math.round(arrival)} />
      </div>
      <div style={{ marginTop: 8, fontSize: 10, color: "#94a3b8" }}>
        {lr && lr.instance_id ? (
          <>
            responder: hired <b style={{ color: "#34d399" }}>+{lr.hired}</b> · durable{" "}
            <span style={{ color: "#64748b" }}>{String(lr.instance_id).slice(0, 12)}…</span>
          </>
        ) : (
          <span style={{ color: "#475569" }}>
            responder idle — inject a surge to trigger the Durable workflow
          </span>
        )}
      </div>
    </div>
  );
}

function Stat({ title, value, hot }: { title: string; value: number | string; hot?: boolean }) {
  return (
    <div
      style={{
        minWidth: 66,
        background: "rgba(2,6,23,0.6)",
        border: `1px solid ${hot ? "rgba(248,113,113,0.55)" : "rgba(56,189,248,0.18)"}`,
        padding: "6px 10px",
        color: hot ? "#fca5a5" : "#e2e8f0",
      }}
    >
      <div style={{ fontSize: 8, textTransform: "uppercase", letterSpacing: 0.8, color: "#64748b" }}>
        {title}
      </div>
      <div style={{ fontSize: 17, fontWeight: 700, marginTop: 2, fontVariantNumeric: "tabular-nums" }}>
        {value}
      </div>
    </div>
  );
}

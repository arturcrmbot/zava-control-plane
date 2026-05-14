/**
 * CeoBadge — top-right HUD prominence for the latest CEO synthesis.
 *
 * Phase H3 of the autonomous-domain-insights v1.1 demo expansion. Shows the
 * latest CEO Insight headline as a persistent warm-gold chip. Subscribes to
 * /api/ticker/stream for live updates and pulses (1.2s gold glow + bounce)
 * whenever a new CEO Insight lands. Polls /api/personas/ceo/insights/latest
 * every 30s as a fallback when SSE is interrupted. Click toggles a popover
 * with the full body + kpis.
 */

import { useEffect, useState } from "react";

type Insight = {
  id: string;
  role: string;
  headline: string;
  body: string;
  kpis: Record<string, unknown>;
  decided_at: string;
};

export function CeoBadge({ enabled = true }: { enabled?: boolean }) {
  const [insight, setInsight] = useState<Insight | null>(null);
  const [pulse, setPulse] = useState(false);
  const [open, setOpen] = useState(false);

  // Initial fetch + 30s poll fallback.
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    const fetchLatest = () => {
      fetch("/api/personas/ceo/insights/latest")
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => {
          if (!cancelled && d) setInsight(d as Insight);
        })
        .catch(() => {});
    };
    fetchLatest();
    const id = setInterval(fetchLatest, 30000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [enabled]);

  // Live SSE subscription — pulse on new CEO insights.
  useEffect(() => {
    if (!enabled) return;
    const es = new EventSource("/api/ticker/stream");
    es.onmessage = (ev) => {
      try {
        const item = JSON.parse(ev.data);
        if (item && item.kind === "Insight" && item.role === "ceo") {
          setInsight(item as Insight);
          setPulse(true);
          setTimeout(() => setPulse(false), 1300);
        }
      } catch {
        /* ignore malformed frames */
      }
    };
    return () => es.close();
  }, [enabled]);

  if (!enabled) return null;

  return (
    <>
      <div
        data-testid="ceo-badge"
        onClick={() => setOpen((o) => !o)}
        style={{
          position: "fixed",
          top: 76,
          right: 16,
          zIndex: 60,
          background: "rgba(8,12,24,0.85)",
          color: "#fff3b8",
          border: "1px solid rgba(255,243,184,0.35)",
          borderRadius: 10,
          padding: "10px 14px",
          font: "12px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace",
          cursor: "pointer",
          maxWidth: 360,
          boxShadow: pulse
            ? "0 0 32px rgba(255,243,184,0.7), 0 0 8px rgba(255,243,184,1)"
            : "0 4px 12px rgba(0,0,0,0.5)",
          transition: "box-shadow 0.5s ease-out",
          animation: pulse ? "ceoPulse 1.2s ease-out" : undefined,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            marginBottom: 4,
          }}
        >
          <span
            style={{
              background: "#fff3b8",
              color: "#1a1408",
              fontSize: 9,
              fontWeight: 700,
              letterSpacing: 1.5,
              padding: "2px 6px",
              borderRadius: 4,
            }}
          >
            CEO
          </span>
          <span
            style={{
              fontSize: 10,
              opacity: 0.7,
              letterSpacing: 1.5,
              textTransform: "uppercase",
            }}
          >
            synthesis
          </span>
        </div>
        <div
          style={{
            fontWeight: 600,
            animation: pulse ? "ceoBounce 1.2s ease-out" : undefined,
          }}
        >
          {insight?.headline || "System online — awaiting domain insights"}
        </div>
      </div>
      {open && insight && (
        <div
          data-testid="ceo-badge-popover"
          style={{
            position: "fixed",
            top: 168,
            right: 16,
            zIndex: 60,
            background: "rgba(8,12,24,0.95)",
            color: "#dbe5ff",
            border: "1px solid rgba(255,243,184,0.35)",
            borderRadius: 10,
            padding: "12px 16px",
            maxWidth: 460,
            font: "12px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace",
            boxShadow: "0 8px 32px rgba(0,0,0,0.6)",
          }}
        >
          <div style={{ marginBottom: 8 }}>{insight.body || "(no detail)"}</div>
          {insight.kpis && Object.keys(insight.kpis).length > 0 && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "auto 1fr",
                gap: "2px 12px",
                opacity: 0.85,
              }}
            >
              {Object.entries(insight.kpis).map(([k, v]) => (
                <span key={k} style={{ display: "contents" }}>
                  <span style={{ opacity: 0.6 }}>{k}</span>
                  <span>{formatKpi(v)}</span>
                </span>
              ))}
            </div>
          )}
        </div>
      )}
      <style>{`
        @keyframes ceoPulse {
          0%   { transform: scale(1); }
          40%  { transform: scale(1.08); }
          100% { transform: scale(1); }
        }
        @keyframes ceoBounce {
          0%   { transform: translateY(0); }
          30%  { transform: translateY(-3px); }
          60%  { transform: translateY(1px); }
          100% { transform: translateY(0); }
        }
      `}</style>
    </>
  );
}

function formatKpi(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(2);
  if (typeof v === "string") return v;
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

import { useState } from "react";
import { loadGuidedJourney } from "./guidedJourney";
import { triggerNarrator } from "./Narrator";

interface StoryGuideProps {
  isReplay: boolean;
  recordedAt?: string;
}

/**
 * StoryGuide — compact fixed overlay that orients first-time viewers of the
 * full-screen Constellation without requiring a presenter.
 *
 * Truthfully distinguishes live runtime from recorded telemetry, guides one
 * cross-functional Aurora decision, names the governance layer, and explains
 * real/synthetic/customer-connection boundaries.
 */
export function StoryGuide({ isReplay, recordedAt }: StoryGuideProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  async function handleJourney() {
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      const result = await loadGuidedJourney(isReplay);
      triggerNarrator(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const statusLabel = isReplay
    ? recordedAt
      ? `Recorded telemetry · ${new Date(recordedAt).toLocaleDateString()}`
      : "Recorded telemetry"
    : "Live runtime";

  return (
    <div
      data-testid="story-guide"
      style={{
        position: "fixed",
        top: 72,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 60,
        maxWidth: "min(560px, 90vw)",
        width: "100%",
        background: "rgba(8,12,32,0.92)",
        border: "1px solid rgba(56,189,248,0.22)",
        borderTop: "1px solid rgba(56,189,248,0.45)",
        borderRadius: 10,
        padding: "14px 18px",
        color: "#e2e8f0",
        fontFamily: "ui-sans-serif, system-ui",
        fontSize: 12,
        boxShadow: "0 8px 36px rgba(0,0,0,0.6), inset 0 1px 0 rgba(56,189,248,0.10)",
        backdropFilter: "blur(12px) saturate(1.3)",
        WebkitBackdropFilter: "blur(12px) saturate(1.3)",
        pointerEvents: "auto",
      }}
    >
      {/* Orientation */}
      <div style={{ fontWeight: 600, fontSize: 13, color: "#f1f5f9", marginBottom: 4 }}>
        You are watching a working agentic organisation.
      </div>
      <div style={{ color: "#94a3b8", lineHeight: 1.5, marginBottom: 8 }}>
        Agents, people, durable workflows, policy and enterprise tools across
        functions — finance, HR, procurement, legal, IT, commercial — all
        coordinated through one shared control plane.
      </div>

      {/* Status + action row */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: error ? 8 : 0 }}>
        <span
          data-testid="story-guide-status"
          style={{
            fontSize: 11,
            color: isReplay ? "#a78bfa" : "#4ade80",
            background: isReplay ? "rgba(167,139,250,0.12)" : "rgba(74,222,128,0.12)",
            border: `1px solid ${isReplay ? "rgba(167,139,250,0.3)" : "rgba(74,222,128,0.3)"}`,
            borderRadius: 999,
            padding: "2px 9px",
            fontWeight: 500,
          }}
        >
          {statusLabel}
        </span>

        <button
          data-testid="story-guide-journey-btn"
          onClick={handleJourney}
          disabled={busy}
          style={{
            padding: "5px 13px",
            background: busy
              ? "rgba(99,102,241,0.3)"
              : "linear-gradient(135deg, #6366f1, #8b5cf6)",
            color: busy ? "#a5b4fc" : "#fff",
            border: "none",
            borderRadius: 6,
            cursor: busy ? "not-allowed" : "pointer",
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: 0.3,
          }}
        >
          {busy ? "Starting…" : "Follow one decision"}
        </button>

        <button
          aria-label={open ? "Hide boundaries" : "Where your systems connect"}
          onClick={() => setOpen((v) => !v)}
          style={{
            background: "none",
            border: "none",
            color: "#64748b",
            cursor: "pointer",
            fontSize: 11,
            padding: "2px 4px",
            textDecoration: "underline",
          }}
        >
          {open ? "Hide" : "Where your systems connect"}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div
          role="alert"
          data-testid="story-guide-error"
          style={{
            marginTop: 6,
            color: "#fca5a5",
            fontSize: 11,
            background: "rgba(239,68,68,0.12)",
            border: "1px solid rgba(239,68,68,0.3)",
            borderRadius: 6,
            padding: "4px 10px",
          }}
        >
          {error}
        </div>
      )}

      {/* Expandable boundaries detail */}
      {open && (
        <details
          open
          data-testid="story-guide-boundaries"
          style={{ marginTop: 10, borderTop: "1px solid rgba(148,163,184,0.12)", paddingTop: 10 }}
        >
          <summary
            style={{
              color: "#67e8f9",
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: 0.5,
              textTransform: "uppercase",
              cursor: "pointer",
              listStyle: "none",
              marginBottom: 6,
            }}
          >
            Where your systems connect
          </summary>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 11 }}>
            <BoundaryRow
              badge="Real"
              color="#4ade80"
              text="Durable workflows, agent sessions, governance, audit, MCP boundaries and runtime events."
            />
            <BoundaryRow
              badge="Synthetic"
              color="#fbbf24"
              text="Organisational records, personae and external systems used to keep the public reference running."
            />
            <BoundaryRow
              badge="Connect"
              color="#38bdf8"
              text="Your existing systems, skills and MCPs, policies, data and people replace the synthetic edges incrementally."
            />
          </div>
        </details>
      )}
    </div>
  );
}

function BoundaryRow({
  badge,
  color,
  text,
}: {
  badge: string;
  color: string;
  text: string;
}) {
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
      <span
        style={{
          flexShrink: 0,
          fontSize: 10,
          fontWeight: 700,
          color,
          background: `${color}18`,
          border: `1px solid ${color}44`,
          borderRadius: 4,
          padding: "1px 6px",
          lineHeight: 1.5,
        }}
      >
        {badge}
      </span>
      <span style={{ color: "#94a3b8", lineHeight: 1.45 }}>{text}</span>
    </div>
  );
}

export default StoryGuide;

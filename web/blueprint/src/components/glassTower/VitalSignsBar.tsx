/**
 * VitalSignsBar — top-of-screen heartbeat strip + burst button.
 *
 * Always-visible. Shows the macro state in big mono numbers so an
 * operator never loses the org-wide picture while exploring the tower.
 */
import { useState } from "react";
import type { VitalSigns } from "../../lib/useLiveOrg";

interface Props {
  status: "watching" | "connecting" | "offline";
  vital: VitalSigns;
}

export function VitalSignsBar({ status, vital }: Props) {
  const [burstBusy, setBurstBusy] = useState(false);

  async function spawnBurst() {
    setBurstBusy(true);
    try {
      await fetch("/api/simulator/inject-burst?n=8", { method: "POST" });
    } finally {
      setTimeout(() => setBurstBusy(false), 1000);
    }
  }

  async function seedKpis() {
    try {
      await fetch("/api/simulator/seed-kpis", { method: "POST" });
    } catch {
      /* ignore */
    }
  }

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        height: 56,
        padding: "0 18px",
        display: "flex",
        alignItems: "center",
        gap: 28,
        background: "linear-gradient(180deg, rgba(6,7,10,0.92) 0%, rgba(6,7,10,0.78) 100%)",
        borderBottom: "1px solid rgba(255,255,255,0.07)",
        color: "#cfd2d6",
        fontFamily: "var(--mono-family, monospace)",
        zIndex: 7,
        backdropFilter: "blur(6px)",
      }}
    >
      <Stat label="IN FLIGHT" value={vital.in_flight} color="#7faed4" />
      <Stat label="AWAITING" value={vital.awaiting} color="#fbbf24" />
      <Stat label="DECIDED · 60s" value={vital.decided_today} color="#a78bfa" />
      <Stat label="EXCEPTIONS" value={vital.exceptions} color={vital.exceptions > 0 ? "#e87a5d" : "#5fd49d"} />
      <Stat label="SLA RISK" value={vital.sla_breaching} color={vital.sla_breaching > 0 ? "#f4a300" : "#5fd49d"} />

      <div style={{ flex: 1 }} />

      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span
          style={{
            display: "inline-block",
            width: 8,
            height: 8,
            borderRadius: 999,
            background: status === "watching" ? "#5fd49d" : status === "connecting" ? "#ffd76a" : "#e87a5d",
            boxShadow: `0 0 8px ${status === "watching" ? "#5fd49d" : status === "connecting" ? "#ffd76a" : "#e87a5d"}`,
          }}
        />
        <span style={{ fontSize: 11, letterSpacing: "0.12em", textTransform: "uppercase" }}>{status}</span>
      </div>

      <button
        type="button"
        onClick={seedKpis}
        style={{
          background: "rgba(20,22,28,0.7)",
          border: "1px solid rgba(207,210,214,0.3)",
          borderRadius: 6,
          padding: "6px 10px",
          color: "#cfd2d6",
          fontFamily: "inherit",
          fontSize: 11,
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          cursor: "pointer",
        }}
      >
        seed kpis
      </button>

      <button
        type="button"
        onClick={spawnBurst}
        disabled={burstBusy}
        style={{
          background: burstBusy ? "rgba(20,22,28,0.5)" : "linear-gradient(180deg, #5fd49d 0%, #3aa67e 100%)",
          border: "1px solid rgba(95,212,157,0.45)",
          borderRadius: 6,
          padding: "6px 14px",
          color: "#04150c",
          fontFamily: "inherit",
          fontSize: 11,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          fontWeight: 600,
          cursor: burstBusy ? "wait" : "pointer",
        }}
      >
        ⚡ burst 8
      </button>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <span
        style={{
          fontSize: 24,
          color,
          fontWeight: 600,
          lineHeight: 1,
          textShadow: `0 0 12px ${color}55`,
        }}
      >
        {value}
      </span>
      <span style={{ fontSize: 10, color: "#9aa0a6", letterSpacing: "0.12em" }}>{label}</span>
    </div>
  );
}

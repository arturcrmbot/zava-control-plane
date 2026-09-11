import type { CosmicMode, PersonaState, WorkflowMoonData } from "../lib/types";
import { PanelPicker } from "./PanelPicker";
import type { ReplayModeInfo } from "../../../lib/useReplayMode";

interface VitalSignsBarProps {
  source: ReplayModeInfo;
  inFlight: WorkflowMoonData[];
  personas: PersonaState[];
  status: string;
  mode: CosmicMode;
  setMode: (mode: CosmicMode) => void;
  onBurst: () => void;
  /** Live counter from flashesRef (read once per second). */
  recentEvents: number;
  /** Workflow completions per minute (computed by parent). */
  throughputPerMin?: number;
}

/** Top HUD: vital signs + ⚡BURST + mode toggle + PANELS picker. */
export function VitalSignsBar(props: VitalSignsBarProps) {
  const {
    inFlight,
    personas,
    status,
    mode,
    setMode,
    onBurst,
    recentEvents,
    source,
  } = props;

  // Throughput is computed by the parent (CosmicLens) which has direct
  // access to flashesRef. Pass via prop.
  const throughput = props.throughputPerMin ?? 0;

  const pendingDecisions = personas.reduce(
    (sum, p) => sum + (p.pending_count ?? 0),
    0,
  );
  const exceptions = inFlight.filter((wf) => wf.active_exception_id).length;

  return (
    <div
      className="cosmic-vitals"
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        padding: "10px 16px",
        display: "flex",
        flexWrap: "wrap",
        gap: "var(--vitals-gap, 16px)",
        alignItems: "center",
        background: "linear-gradient(to bottom, rgba(2,6,23,0.92), rgba(2,6,23,0.65))",
        color: "#e2e8f0",
        fontFamily: "ui-sans-serif, system-ui",
        fontSize: 12,
        zIndex: 20,
        borderBottom: "1px solid rgba(148,163,184,0.12)",
      }}
    >
      <Stat label="Active cases" value={inFlight.length} accent="#22d3ee" />
      <Divider />
      <Stat label="Awaiting people" value={pendingDecisions} accent="#fb923c" />
      <Divider />
      <Stat label="Steps per minute" value={throughput.toFixed(1)} accent="#a78bfa" />
      <Divider />
      <Stat
        label="Stuck at a person"
        value={exceptions}
        accent={exceptions > 0 ? "#f59e0b" : "#475569"}
      />
      <Divider />
      <Stat label="Events per minute" value={Math.round(recentEvents)} accent="#10b981" />

      <div className="cosmic-vitals__spacer" style={{ flex: 1 }} />

      <StatusPill status={status} source={source} />

      {source.mode === "live" && (
        <button onClick={onBurst} style={btnStyle("primary")} title="Inject 8 varied workflows">
          ⚡ Spawn 8 cases
        </button>
      )}

      <ModeToggle mode={mode} setMode={setMode} />

      {/* PANELS picker — last in the row, gets the same 16px gap as
          everything else. Lives INSIDE the bar so it never overlaps the
          mode toggle and never shifts when its dropdown opens (the
          dropdown is absolutely-positioned beneath the chip). */}
      <PanelPicker />
    </div>
  );
}

function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: number | string;
  accent: string;
}) {
  return (
    <div className="cosmic-vitals__stat" style={{ display: "flex", flexDirection: "column", lineHeight: 1.1 }}>
      <span
        style={{
          color: accent,
          fontSize: 18,
          fontWeight: 600,
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {value}
      </span>
      <span style={{ color: "#94a3b8", fontSize: 10, textTransform: "uppercase", letterSpacing: 0.5 }}>
        {label}
      </span>
    </div>
  );
}

function Divider() {
  return (
    <div
      className="cosmic-vitals__divider"
      style={{
        width: 1,
        height: 30,
        background: "rgba(148,163,184,0.15)",
      }}
    />
  );
}

function StatusPill({ status, source }: { status: string; source: ReplayModeInfo }) {
  let color: string;
  let label: string;
  let titleAttr: string | undefined;
  if (source.mode === "loading" || source.mode === "unavailable") {
    color = "#fbbf24";
    label = source.mode === "loading" ? "Checking source…" : "Source unavailable";
    titleAttr = source.mode === "unavailable" ? source.error : undefined;
  } else if (source.mode === "replay") {
    const { recordedAt } = source;
    color = "#a78bfa";
    const stamp = recordedAt ? new Date(recordedAt).toLocaleDateString() : "";
    label = stamp ? `Replay · ${stamp}` : "Replay";
    titleAttr = recordedAt
      ? `Recorded telemetry from ${recordedAt}; not live`
      : "Recorded telemetry; not live";
  } else {
    color =
      status === "watching" ? "#4ade80" : status === "connecting" ? "#fb923c" : "#ef4444";
    label =
      status === "watching" ? "Live" : status === "connecting" ? "Connecting…" : "Disconnected";
  }
  return (
    <div
      title={titleAttr}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "4px 10px",
        background: "rgba(15,23,42,0.7)",
        border: `1px solid ${color}40`,
        borderRadius: 999,
        color,
        fontSize: 11,
        fontWeight: 500,
      }}
    >
      <span
        style={{
          width: 7,
          height: 7,
          background: color,
          borderRadius: "50%",
          boxShadow: `0 0 8px ${color}`,
        }}
      />
      {label}
    </div>
  );
}

function ModeToggle({
  mode,
  setMode,
}: {
  mode: CosmicMode;
  setMode: (m: CosmicMode) => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        background: "rgba(15,23,42,0.7)",
        border: "1px solid rgba(148,163,184,0.2)",
        borderRadius: 6,
        overflow: "hidden",
      }}
    >
      <ToggleBtn
        active={mode === "capabilities"}
        onClick={() => setMode("capabilities")}
        title="Show me what's being done"
      >
        Capabilities
      </ToggleBtn>
      <ToggleBtn
        active={mode === "entities"}
        onClick={() => setMode("entities")}
        title="Show me which records are being touched"
      >
        Entities
      </ToggleBtn>
    </div>
  );
}

function ToggleBtn({
  active,
  onClick,
  title,
  children,
}: {
  active: boolean;
  onClick: () => void;
  title?: string;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      style={{
        padding: "6px 12px",
        background: active ? "linear-gradient(135deg, #6366f1, #8b5cf6)" : "transparent",
        color: active ? "#fff" : "#cbd5e1",
        border: "none",
        cursor: "pointer",
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: 0.3,
      }}
    >
      {children}
    </button>
  );
}

function btnStyle(kind: "primary" | "secondary"): React.CSSProperties {
  if (kind === "primary") {
    return {
      padding: "7px 12px",
      background: "linear-gradient(135deg, #6366f1, #ec4899)",
      color: "white",
      border: "none",
      borderRadius: 6,
      cursor: "pointer",
      fontSize: 11,
      fontWeight: 700,
      letterSpacing: 0.3,
    };
  }
  return {
    padding: "7px 10px",
    background: "rgba(30,41,59,0.6)",
    color: "#94a3b8",
    border: "1px solid rgba(148,163,184,0.18)",
    borderRadius: 6,
    cursor: "pointer",
    fontSize: 10,
    fontWeight: 500,
  };
}

/**
 * PersonaStrip — bottom HUD showing every persona's current state.
 *
 * Horizontal scrolling row of small cards: state pill + role + last
 * action summary. Updates as personas.* SSE events flow.
 */
import type { PersonaRow } from "../../lib/useLiveOrg";

interface Props {
  personas: PersonaRow[];
}

const STATE_PALETTE: Record<PersonaRow["state"], { bg: string; dot: string; label: string }> = {
  working: { bg: "rgba(251,191,36,0.18)", dot: "#fbbf24", label: "WORKING" },
  recently_decided: { bg: "rgba(95,212,157,0.18)", dot: "#5fd49d", label: "DECIDED" },
  idle: { bg: "rgba(154,160,166,0.12)", dot: "#9aa0a6", label: "IDLE" },
};

export function PersonaStrip({ personas }: Props) {
  if (personas.length === 0) return null;

  return (
    <div
      style={{
        position: "absolute",
        bottom: 0,
        left: 0,
        right: 0,
        height: 88,
        padding: "8px 18px",
        display: "flex",
        alignItems: "center",
        gap: 10,
        overflowX: "auto",
        background: "linear-gradient(0deg, rgba(6,7,10,0.95) 0%, rgba(6,7,10,0.78) 100%)",
        borderTop: "1px solid rgba(255,255,255,0.07)",
        color: "#cfd2d6",
        fontFamily: "var(--mono-family, monospace)",
        zIndex: 7,
        backdropFilter: "blur(6px)",
      }}
    >
      <div
        style={{
          fontSize: 9,
          letterSpacing: "0.16em",
          color: "#9aa0a6",
          marginRight: 6,
          minWidth: 60,
          textTransform: "uppercase",
        }}
      >
        Personas
        <br />
        <span style={{ color: "#cfd2d6" }}>{personas.length}</span>
      </div>
      {personas.map((p) => {
        const palette = STATE_PALETTE[p.state] ?? STATE_PALETTE.idle;
        const last = p.last_decision;
        return (
          <div
            key={p.role}
            title={`${p.role} · ${p.state}`}
            style={{
              minWidth: 130,
              padding: "8px 10px",
              borderRadius: 6,
              background: palette.bg,
              border: `1px solid ${palette.dot}40`,
              display: "flex",
              flexDirection: "column",
              gap: 4,
              flex: "0 0 auto",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span
                style={{
                  display: "inline-block",
                  width: 7,
                  height: 7,
                  borderRadius: 999,
                  background: palette.dot,
                  boxShadow: `0 0 5px ${palette.dot}`,
                }}
              />
              <span
                style={{
                  fontSize: 9,
                  letterSpacing: "0.12em",
                  color: palette.dot,
                  textTransform: "uppercase",
                  fontWeight: 600,
                }}
              >
                {palette.label}
              </span>
              {p.pending_count > 0 && (
                <span
                  style={{
                    marginLeft: "auto",
                    fontSize: 9,
                    background: "#fbbf24",
                    color: "#04050a",
                    padding: "1px 5px",
                    borderRadius: 4,
                    fontWeight: 600,
                  }}
                >
                  {p.pending_count}
                </span>
              )}
            </div>
            <div style={{ fontSize: 11, color: "#f5f5f7", fontWeight: 500 }}>{p.role}</div>
            <div style={{ fontSize: 9, color: "#9aa0a6" }}>
              {last && last.workflow_id
                ? `${last.verdict ?? "?"} · ${last.workflow_id}`
                : p.pending_count > 0
                ? `${p.pending[0]?.workflow_id ?? "?"}`
                : "—"}
            </div>
          </div>
        );
      })}
    </div>
  );
}

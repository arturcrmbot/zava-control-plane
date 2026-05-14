/**
 * PanelPicker — a small chip top-right that opens a checklist of HUD panels
 * AND the ambient-music toggle. Click a row to toggle its visibility / its
 * play state. Persisted via usePanelVisibility / useAmbientMusic.
 *
 * Always renders its trigger chip even when everything else is hidden, so
 * the user can always get back.
 */
import { useState } from "react";
import { usePanelVisibility, type PanelId } from "./usePanelVisibility";
import { useAmbientMusic } from "./useAmbientMusic";

// Vital signs (the top bar) is intentionally NOT toggleable: it hosts this
// PanelPicker chip itself, so hiding it would strand the user with no way
// to bring panels back. The other panels are safe to toggle.
const PANELS: { id: PanelId; label: string }[] = [
  { id: "narrative-arcs", label: "Cast" },
  { id: "knowledge-pulse", label: "Knowledge pulse (entities mode)" },
  { id: "activity-rail", label: "Activity rail (incl. busiest teams)" },
  { id: "time-scrub", label: "Time scrub slider" },
];

export function PanelPicker() {
  const { visible, toggle, hidden, showAll, hideAll } = usePanelVisibility();
  const music = useAmbientMusic();
  const [open, setOpen] = useState(false);
  const hiddenCount = hidden.size;

  return (
    <div
      data-testid="panel-picker"
      style={{
        // Now placed INSIDE VitalSignsBar's flex row — so it sits in
        // perfect rhythm with the other top-bar buttons (Live, Spawn,
        // Capabilities/Entities) instead of floating off in the corner.
        // Wrapper is position:relative so the dropdown can absolute-position
        // beneath the chip without disturbing flex flow.
        position: "relative",
        fontFamily: "ui-sans-serif, system-ui",
        fontSize: 12,
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        title={hiddenCount > 0 ? `Panels (${hiddenCount} hidden)` : "Panels"}
        style={{
          all: "unset",
          cursor: "pointer",
          // Fixed width so the chip NEVER changes size when its contents
          // change. State (any panels hidden?) is signalled via colour +
          // glow only — no inline badge that would resize the chip.
          boxSizing: "border-box",
          width: 116,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 6,
          padding: "6px 10px",
          background: "rgba(2,6,23,0.86)",
          border: hiddenCount > 0
            ? "1px solid rgba(34,211,238,0.45)"
            : "1px solid rgba(148,163,184,0.25)",
          borderRadius: 6,
          color: hiddenCount > 0 ? "#67e8f9" : "#cbd5e1",
          fontWeight: 600,
          letterSpacing: 0.4,
          fontSize: 11,
          textTransform: "uppercase",
          backdropFilter: "blur(6px)",
          boxShadow: hiddenCount > 0 ? "0 0 10px rgba(34,211,238,0.18)" : "none",
        }}
      >
        <span aria-hidden>☰</span>
        <span>Panels</span>
      </button>

      {open ? (
        <div
          role="menu"
          style={{
            // Absolute-positioned beneath the chip so opening the dropdown
            // doesn't shove other top-bar buttons leftward.
            position: "absolute",
            top: "100%",
            right: 0,
            marginTop: 6,
            background: "rgba(2,6,23,0.92)",
            border: "1px solid rgba(148,163,184,0.22)",
            borderRadius: 8,
            padding: 6,
            minWidth: 240,
            boxShadow: "0 8px 24px rgba(0,0,0,0.45)",
            backdropFilter: "blur(6px)",
            zIndex: 80,
          }}
        >
          {PANELS.map((p) => {
            const isVisible = visible(p.id);
            return (
              <button
                key={p.id}
                type="button"
                role="menuitemcheckbox"
                aria-checked={isVisible}
                onClick={() => toggle(p.id)}
                style={{
                  all: "unset",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  width: "100%",
                  boxSizing: "border-box",
                  padding: "5px 8px",
                  borderRadius: 4,
                  color: isVisible ? "#e2e8f0" : "#64748b",
                  fontSize: 12,
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.background = "rgba(148,163,184,0.10)";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.background = "transparent";
                }}
              >
                <span aria-hidden style={{ display: "inline-block", width: 14 }}>
                  {isVisible ? "☑" : "☐"}
                </span>
                <span style={{ flex: 1, textAlign: "left" }}>{p.label}</span>
              </button>
            );
          })}

          {/* Ambient music — same row affordance as the panels above so
              there's only ONE chip in the corner instead of two competing
              for space. */}
          <button
            key="music"
            type="button"
            role="menuitemcheckbox"
            aria-checked={music.enabled}
            onClick={music.toggle}
            style={{
              all: "unset",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 8,
              width: "100%",
              boxSizing: "border-box",
              padding: "5px 8px",
              marginTop: 4,
              borderTop: "1px solid rgba(148,163,184,0.15)",
              borderRadius: 4,
              color: music.enabled ? "#67e8f9" : "#64748b",
              fontSize: 12,
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.background = "rgba(148,163,184,0.10)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.background = "transparent";
            }}
          >
            <span aria-hidden style={{ display: "inline-block", width: 14 }}>
              {music.enabled ? "☑" : "☐"}
            </span>
            <span style={{ flex: 1, textAlign: "left" }}>♪ Ambient music</span>
          </button>

          {hiddenCount > 0 ? (
            <button
              type="button"
              onClick={showAll}
              style={{
                all: "unset",
                cursor: "pointer",
                display: "block",
                width: "100%",
                boxSizing: "border-box",
                marginTop: 4,
                padding: "5px 8px",
                borderTop: "1px solid rgba(148,163,184,0.15)",
                color: "#67e8f9",
                fontSize: 11,
                textAlign: "center",
                letterSpacing: 0.4,
                textTransform: "uppercase",
                fontWeight: 600,
              }}
            >
              Show all
            </button>
          ) : (
            <button
              type="button"
              onClick={hideAll}
              style={{
                all: "unset",
                cursor: "pointer",
                display: "block",
                width: "100%",
                boxSizing: "border-box",
                marginTop: 4,
                padding: "5px 8px",
                borderTop: "1px solid rgba(148,163,184,0.15)",
                color: "#94a3b8",
                fontSize: 11,
                textAlign: "center",
                letterSpacing: 0.4,
                textTransform: "uppercase",
                fontWeight: 600,
              }}
            >
              Hide all
            </button>
          )}
        </div>
      ) : null}
    </div>
  );
}

export default PanelPicker;

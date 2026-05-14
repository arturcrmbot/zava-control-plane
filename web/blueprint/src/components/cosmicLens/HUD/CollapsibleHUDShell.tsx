/**
 * CollapsibleHUDShell — wraps any HUD panel with a click-to-toggle header,
 * an absolute-positioned anchor (top/bottom/left/right) or 'stacked' for
 * placement inside HUDLeftStack, and an internally scrollable body capped
 * at a fraction of the viewport.
 *
 * Why this exists: the HUD panels (Cast, Knowledge Pulse) were absolute-
 * positioned slabs blocking the scene and each other on a Mac trackpad.
 * This shell:
 *   - lets the user collapse any panel to a one-line strip,
 *   - caps body height at `maxBodyVh` (default 40vh) with overflow-y:auto,
 *   - persists collapsed state in localStorage so a refresh doesn't re-open
 *     everything the user had hidden,
 *   - exposes minimal CSS so the existing panel content keeps working.
 */
import { useEffect, useRef, useState, type ReactNode } from "react";

export type HUDAnchor = "top" | "bottom" | "left" | "right" | "top-right" | "top-left" | "bottom-right" | "bottom-left" | "stacked";

interface Props {
  id: string;                         // localStorage key — must be stable per panel
  title: string;                      // shown in the header strip
  badge?: string;                     // optional small chip (e.g. count)
  anchor: HUDAnchor;
  defaultCollapsed?: boolean;
  width?: number | string;            // defaults to fit-content / per-anchor sensible
  maxBodyVh?: number;                 // default 40
  children: ReactNode;
}

const STORAGE_PREFIX = "zava.hud.collapsed.";

function anchorStyle(anchor: HUDAnchor, width: Props["width"]): React.CSSProperties {
  // VitalSignsBar is a fixed strip at top:0; agency-pack HUD lives BELOW it.
  // Bottom anchors give space for the TimeScrub slider pinned at the very bottom.
  const TOP_OFFSET = 64;
  const BOTTOM_OFFSET = 56;
  const base: React.CSSProperties = {
    position: "absolute",
    // Open panels render ABOVE the PANELS chip (z=60) so the user can
    // actually read them without the chip overlay covering corner content.
    // The chip's dropdown still appears above panels because it sets its
    // own higher z when open via the menu role styling.
    zIndex: 70,
    width: width ?? undefined,
    maxWidth: "min(100vw - 32px, 480px)",
    pointerEvents: "auto",
  };
  switch (anchor) {
    case "stacked":
      // No positioning — the parent HUDLeftStack flex container places it.
      return {
        position: "static",
        zIndex: undefined,
        width: width ?? "100%",
        maxWidth: "100%",
        pointerEvents: "auto",
      };
    case "top":
    case "top-left":
      return { ...base, top: TOP_OFFSET, left: 12 };
    case "top-right":
      return { ...base, top: TOP_OFFSET, right: 12 };
    case "bottom":
    case "bottom-left":
      return { ...base, bottom: BOTTOM_OFFSET, left: 12 };
    case "bottom-right":
      return { ...base, bottom: BOTTOM_OFFSET, right: 12 };
    case "left":
      return { ...base, top: "50%", left: 12, transform: "translateY(-50%)" };
    case "right":
      return { ...base, top: "50%", right: 12, transform: "translateY(-50%)" };
    default:
      return base;
  }
}

/**
 * HUDLeftStack — single absolute container that stacks its CollapsibleHUDShell
 * children vertically on the left edge of the screen, between VitalSignsBar
 * and TimeScrub. Avoids fighting the existing ActivityRail (right edge) and
 * WorkflowDrawer.
 */
export function HUDLeftStack({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        position: "absolute",
        top: 64,
        bottom: 56,
        left: 12,
        width: 320,
        zIndex: 30,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        pointerEvents: "none",      // shell children re-enable pointerEvents
        overflowY: "auto",          // if more panels than viewport, the column scrolls
        overflowX: "hidden",
        scrollbarWidth: "thin",
      }}
    >
      {children}
    </div>
  );
}

export function CollapsibleHUDShell({
  id,
  title,
  badge,
  anchor,
  defaultCollapsed = false,
  width,
  maxBodyVh = 40,
  children,
}: Props) {
  const storageKey = STORAGE_PREFIX + id;
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (raw === "1") return true;
      if (raw === "0") return false;
    } catch {
      /* ignore */
    }
    return defaultCollapsed;
  });

  useEffect(() => {
    try {
      window.localStorage.setItem(storageKey, collapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [collapsed, storageKey]);

  const ref = useRef<HTMLDivElement | null>(null);

  return (
    <div
      ref={ref}
      data-hud-shell={id}
      style={{
        ...anchorStyle(anchor, width),
        // Glassy gradient backdrop with cyan-tinged inner highlight on the
        // top edge — reads as a sci-fi command HUD frame rather than a
        // generic dark slab. The 1px cyan inner top is the signature touch.
        background:
          "linear-gradient(180deg, rgba(8, 12, 32, 0.82) 0%, rgba(2, 6, 23, 0.78) 100%)",
        border: "1px solid rgba(56,189,248,0.15)",
        borderTop: "1px solid rgba(56,189,248,0.32)",
        borderRadius: 6,
        boxShadow:
          "0 8px 30px rgba(0,0,0,0.45), inset 0 1px 0 rgba(56,189,248,0.10)",
        color: "#e2e8f0",
        fontFamily: "ui-sans-serif, system-ui",
        fontSize: 12,
        backdropFilter: "blur(10px) saturate(1.2)",
        WebkitBackdropFilter: "blur(10px) saturate(1.2)",
        overflow: "hidden",
      }}
    >
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        aria-expanded={!collapsed}
        title={collapsed ? "Expand" : "Collapse"}
        style={{
          all: "unset",
          cursor: "pointer",
          width: "100%",
          boxSizing: "border-box",
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "7px 11px 6px",
          background:
            "linear-gradient(180deg, rgba(15,23,42,0.55) 0%, rgba(15,23,42,0.18) 100%)",
          borderBottom: collapsed
            ? "none"
            : "1px solid rgba(56,189,248,0.18)",
          // Monospace title with wide letter-spacing — Mass Effect / blueprint
          // chrome. Eye-friendly, reads as 'instrument label' not 'web copy'.
          fontFamily: "ui-monospace, SFMono-Regular, 'Roboto Mono', monospace",
          fontWeight: 600,
          letterSpacing: "0.18em",
          fontSize: 10.5,
          textTransform: "uppercase",
          color: "#cbd5e1",
          textShadow: "0 0 10px rgba(56,189,248,0.18)",
        }}
      >
        <span
          aria-hidden
          style={{
            display: "inline-block",
            width: 10,
            color: "#67e8f9",
            textShadow: "0 0 6px rgba(34,211,238,0.6)",
          }}
        >
          {collapsed ? "▸" : "▾"}
        </span>
        <span
          style={{
            flex: 1,
            minWidth: 0,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {title}
        </span>
        {badge ? (
          <span
            style={{
              fontSize: 10,
              padding: "1px 7px",
              borderRadius: 999,
              background: "rgba(34,211,238,0.18)",
              border: "1px solid rgba(34,211,238,0.32)",
              color: "#67e8f9",
              fontWeight: 500,
              letterSpacing: "0.05em",
              textTransform: "none",
              fontFamily: "ui-sans-serif, system-ui",
              boxShadow: "0 0 8px rgba(34,211,238,0.18)",
            }}
          >
            {badge}
          </span>
        ) : null}
      </button>
      {collapsed ? null : (
        <div
          data-hud-body={id}
          style={{
            maxHeight: `${maxBodyVh}vh`,
            overflowY: "auto",
            overflowX: "hidden",
            padding: 9,
            // give the scroll thumb a quiet style on Mac trackpads
            scrollbarWidth: "thin",
            // Subtle scanline texture in the body — barely visible, but it
            // ties everything to the 'instrument readout' aesthetic.
            backgroundImage:
              "repeating-linear-gradient(0deg, rgba(148,163,184,0.025) 0, rgba(148,163,184,0.025) 1px, transparent 1px, transparent 3px)",
          }}
        >
          {children}
        </div>
      )}
    </div>
  );
}

export default CollapsibleHUDShell;

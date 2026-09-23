/**
 * Standalone full-screen Cosmic Lens v2 page.
 *
 * No editorial chrome — just the visual + a minimal HUD strip. Addressable
 * at /?view=constellation. Designed to be projected, recorded, or shown
 * full-bleed during a pitch.
 *
 * When loaded with `?view=constellation&embed=1` the "← back to blueprint"
 * link is suppressed — used when the control plane iframes this view, so
 * the link doesn't navigate the iframe back to the editorial blueprint.
 */

import { useCallback, useEffect, useState } from "react";
import { CosmicLens } from "../components/cosmicLens/CosmicLens";
import { DemoHUD } from "../components/cosmicLens/HUD/DemoHUD";
import { DecisionTicker } from "../components/cosmicLens/HUD/DecisionTicker";
import { PolicyRipple } from "../components/cosmicLens/HUD/PolicyRipple";
import { Narrator } from "../components/cosmicLens/HUD/Narrator";
import { useReplayMode } from "../lib/useReplayMode";
import { getDemoUrl } from "../lib/useDemoUrl";
import type { GuidedJourney } from "../components/cosmicLens/HUD/guidedJourney";

const NAV_LINK_STYLE = {
  color: "#e2e8f0",
  fontSize: 12,
  fontFamily: "ui-sans-serif, system-ui",
  textDecoration: "none",
  padding: "6px 12px",
  borderRadius: 999,
  border: "1px solid rgba(148, 163, 184, 0.35)",
  background: "rgba(15, 23, 42, 0.72)",
} as const;
const SECONDARY_LINK_STYLE = {
  color: "rgba(148, 163, 184, 0.7)",
  fontSize: 12,
  fontFamily: "ui-sans-serif, system-ui",
  textDecoration: "none",
} as const;

/** The operator console owns the control plane. getDemoUrl resolves it
 *  locally (:5275 → :5273) and when deployed; a malformed configured URL
 *  must not take the whole constellation down with it. */
function controlPlaneHref(): string {
  try {
    return getDemoUrl("constellation");
  } catch {
    return "/";
  }
}

export function ConstellationPage() {
  // The blueprint is a pure client-side Vite app (no SSR), so reading
  // window.location.search synchronously on render is safe.
  const params = new URLSearchParams(window.location.search);
  const embed = params.get("embed") === "1";
  const fromFleet = params.get("from") === "fleet";
  const demoEnabled = params.get("demo") === "1";

  const { source } = useReplayMode();
  const sourceKnown = source.mode === "live" || source.mode === "replay";
  const [journey, setJourney] = useState<GuidedJourney | null>(null);
  const [workflowToOpen, setWorkflowToOpen] = useState<string | null>(null);
  const workflowOpened = useCallback(() => setWorkflowToOpen(null), []);
  const inspectWorkflow = useCallback((id: string) => {
    setWorkflowToOpen(id);
    setJourney(null);
  }, []);

  useEffect(() => {
    document.body.classList.add("constellation-page-body");
    return () => {
      document.body.classList.remove("constellation-page-body");
    };
  }, []);

  return (
    <div className="constellation-page">
      <CosmicLens embed={embed} source={source} workflowToOpen={workflowToOpen} onWorkflowOpened={workflowOpened} />
      <DemoHUD enabled={demoEnabled && source.mode === "live"} onFollow={setJourney} />
      <DecisionTicker enabled={sourceKnown} isReplay={source.mode === "replay"} />
      <PolicyRipple enabled={true} />
      {journey && journey.source === source.mode && (
        <Narrator
          key={journey.workflowId}
          journey={journey}
          onClose={() => setJourney(null)}
          onInspect={inspectWorkflow}
        />
      )}
      {!embed && (
        <nav
          className="constellation-page__return"
          aria-label="Views"
          style={{
            position: "absolute",
            bottom: 16,
            left: 16,
            zIndex: 10,
            display: "flex",
            alignItems: "center",
            gap: 14,
          }}
        >
          <a href={controlPlaneHref()} data-testid="open-control-plane" style={NAV_LINK_STYLE}>
            {fromFleet ? "← back to control plane" : "Open control plane →"}
          </a>
          {!fromFleet && (
            <a href="/" style={SECONDARY_LINK_STYLE}>
              blueprint
            </a>
          )}
        </nav>
      )}
    </div>
  );
}

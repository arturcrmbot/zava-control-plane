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
import { StoryGuide } from "../components/cosmicLens/HUD/StoryGuide";
import { useReplayMode } from "../lib/useReplayMode";
import type { GuidedJourney } from "../components/cosmicLens/HUD/guidedJourney";

// Operator console (web/client) lives on port 5273 in dev/preview. When the
// constellation is opened from the operator console (?from=fleet), the back
// link navigates back there instead of to the editorial blueprint page.
function fleetUrl(): string {
  if (typeof window === "undefined") return "/";
  const { protocol, hostname, port } = window.location;
  if (port === "5275") return `${protocol}//${hostname}:5273/`;
  return "/";
}

export function ConstellationPage() {
  // The blueprint is a pure client-side Vite app (no SSR), so reading
  // window.location.search synchronously on render is safe.
  const params = new URLSearchParams(window.location.search);
  const embed = params.get("embed") === "1";
  const fromFleet = params.get("from") === "fleet";
  const demoEnabled = params.get("demo") === "1";

  const { source, retry } = useReplayMode();
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
      <StoryGuide source={source} onRetry={retry} onFollow={setJourney} />
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
        <div
          className="constellation-page__return"
          style={{ position: "absolute", bottom: 16, left: 16, zIndex: 10 }}
        >
          <a
            href={fromFleet ? fleetUrl() : "/"}
            style={{
              color: "rgba(148, 163, 184, 0.7)",
              fontSize: 12,
              fontFamily: "ui-sans-serif, system-ui",
              textDecoration: "none",
            }}
          >
            {fromFleet ? "← back to fleet" : "← back to blueprint"}
          </a>
        </div>
      )}
    </div>
  );
}

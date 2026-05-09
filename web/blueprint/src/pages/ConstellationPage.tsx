/**
 * Standalone full-screen Org-Building / Cosmic-Constellation page.
 *
 * Default lens: the Org Building (zoom-3 backbone). A bottom-right
 * toggle swaps to the legacy Cosmic Constellation lens, preserved as
 * an always-available alternate view per the spec.
 *
 * Chunk 3 (IP6/7/8): wires the four-level zoom — at zoom-2 the
 * underlying OrgBuilding renders the wing LOD treatment; at zoom-1 we
 * mount `<DepartmentInterior>` over it; at zoom-0 we mount
 * `<WorkflowZoom>`. ESC zooms back out one level.
 */

import { useEffect, useState } from "react";
import { CosmicConstellation } from "../components/CosmicConstellation";
import { OrgBuilding } from "../components/OrgBuilding";
import { DepartmentInterior } from "../components/orgBuilding/DepartmentInterior";
import { EventFeed } from "../components/orgBuilding/EventFeed";
import { WorkflowZoom } from "../components/orgBuilding/WorkflowZoom";
import { useObservatory } from "../lib/useObservatory";
import { useOrgZoom } from "../lib/orgZoom";

type Lens = "building" | "cosmic";

export function ConstellationPage() {
  const { status } = useObservatory({ bufferSize: 1 });
  const zoom = useOrgZoom();
  const [lens, setLens] = useState<Lens>("building");

  const embed =
    new URLSearchParams(window.location.search).get("embed") === "1";

  useEffect(() => {
    document.body.classList.add("constellation-page-body");
    return () => {
      document.body.classList.remove("constellation-page-body");
    };
  }, []);

  // ESC zooms out one level (chunk-3 wire-up). At zoom-3 the hook is a
  // no-op; lower levels bubble back up — workflow → org, department →
  // wing, wing → org.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") zoom.zoomOut();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [zoom]);

  return (
    <div className="constellation-page">
      {lens === "building" ? (
        <OrgBuilding status={status} fullScreen zoomTarget={zoom.target} />
      ) : (
        <CosmicConstellation status={status} fullScreen />
      )}

      {/* Department interior — zoom-1 overlay (chunk-3 IP7). */}
      {lens === "building" && zoom.target.kind === "department" && zoom.target.id && (
        <DepartmentInterior
          name={zoom.target.id}
          onClose={() => zoom.zoomOut()}
        />
      )}

      {/* Workflow detail — zoom-0 overlay (chunk-3 IP8). */}
      {lens === "building" && zoom.target.kind === "workflow" && zoom.target.id && (
        <WorkflowZoom
          id={zoom.target.id}
          onClose={() => zoom.zoomOut()}
        />
      )}

      {/* Right-rail event feed — sticky across lens swaps so the
          observatory stream stays visible whenever the org-building
          scene is active. Hidden at zoom-0 (workflow) where the
          WorkflowZoom panel owns the right side. */}
      {lens === "building" && zoom.target.kind !== "workflow" && <EventFeed />}

      <div className="constellation-page__title">
        <div className="constellation-page__eyebrow">the substrate, running</div>
        {!embed && (
          <div className="constellation-page__return">
            <a href="/">← return to the page</a>
          </div>
        )}
      </div>

      {/* Bottom-right lens toggle. */}
      <button
        type="button"
        onClick={() =>
          setLens((cur) => (cur === "building" ? "cosmic" : "building"))
        }
        className="org-building__lens-toggle"
        style={{
          position: "absolute",
          bottom: 16,
          right: 16,
          padding: "8px 14px",
          background: "rgba(10,10,12,0.7)",
          border: "1px solid rgba(207,210,214,0.3)",
          borderRadius: 999,
          color: "#cfd2d6",
          fontFamily: "var(--mono-family, monospace)",
          fontSize: 11,
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          cursor: "pointer",
          zIndex: 7,
        }}
      >
        {lens === "building" ? "Cosmic lens" : "Building lens"}
      </button>
    </div>
  );
}

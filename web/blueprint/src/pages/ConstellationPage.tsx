/**
 * Standalone full-screen Org-Building / Cosmic-Constellation page.
 *
 * Default lens: the Org Building (zoom-3 backbone). A bottom-right
 * toggle swaps to the legacy Cosmic Constellation lens, preserved as
 * an always-available alternate view per the spec.
 *
 * Routing: addressable at /?view=constellation (the URL is unchanged
 * for back-compat — the page itself is what evolved). With
 * `?view=constellation&embed=1` the "← return to the page" link is
 * suppressed.
 */

import { useEffect, useState } from "react";
import { CosmicConstellation } from "../components/CosmicConstellation";
import { OrgBuilding } from "../components/OrgBuilding";
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

  // ESC zooms out. At zoom-3 with the cosmic lens off, useOrgZoom.zoomOut
  // clamps at level 3 (no lower scenes are shipped yet) — the keyboard
  // shortcut is still wired so chunks 2-4 can drop the lower zooms in
  // without revisiting this handler.
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
        <OrgBuilding status={status} fullScreen />
      ) : (
        <CosmicConstellation status={status} fullScreen />
      )}

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

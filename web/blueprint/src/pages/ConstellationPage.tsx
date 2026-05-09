/**
 * Glass Tower page — the agentic org as a living building.
 *
 * Default lens: <GlassTower />. Bottom-right toggle swaps in the legacy
 * <CosmicConstellation /> lens for the original pitch aesthetic.
 */
import { useEffect, useState } from "react";
import { CosmicConstellation } from "../components/CosmicConstellation";
import { GlassTower } from "../components/glassTower/GlassTower";
import { useObservatory } from "../lib/useObservatory";

type Lens = "tower" | "cosmic";

export function ConstellationPage() {
  const { status } = useObservatory({ bufferSize: 1 });
  const [lens, setLens] = useState<Lens>("tower");
  const embed = new URLSearchParams(window.location.search).get("embed") === "1";

  useEffect(() => {
    document.body.classList.add("constellation-page-body");
    return () => {
      document.body.classList.remove("constellation-page-body");
    };
  }, []);

  return (
    <div className="constellation-page">
      {lens === "tower" ? (
        <GlassTower status={status} />
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

      <button
        type="button"
        onClick={() => setLens((cur) => (cur === "tower" ? "cosmic" : "tower"))}
        aria-label={lens === "tower" ? "Switch to cosmic-lens view" : "Switch to glass-tower view"}
        title={lens === "tower" ? "Switch to cosmic-lens view" : "Switch to glass-tower view"}
        style={{
          position: "absolute",
          bottom: 16,
          right: 16,
          padding: "8px 16px",
          background: "rgba(10,10,12,0.78)",
          border: "1px solid rgba(207,210,214,0.45)",
          borderRadius: 999,
          color: "#f5f5f7",
          fontFamily: "var(--mono-family, monospace)",
          fontSize: 11,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          cursor: "pointer",
          zIndex: 9,
          backdropFilter: "blur(6px)",
          boxShadow: "0 2px 12px rgba(0,0,0,0.35)",
        }}
      >
        {lens === "tower" ? "◌ Cosmic lens" : "▣ Tower lens"}
      </button>
    </div>
  );
}

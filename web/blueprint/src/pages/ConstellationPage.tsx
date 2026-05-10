/**
 * Standalone full-screen Cosmic Lens v2 page.
 *
 * No editorial chrome — just the visual + a minimal HUD strip. Addressable
 * at /?view=constellation. Designed to be projected, recorded, or shown
 * full-bleed during a pitch.
 *
 * When loaded with `?view=constellation&embed=1` the "← return to the page"
 * link is suppressed — used when the control plane iframes this view, so
 * the link doesn't navigate the iframe back to the editorial blueprint.
 */

import { useEffect } from "react";
import { CosmicLens } from "../components/cosmicLens/CosmicLens";

export function ConstellationPage() {
  // The blueprint is a pure client-side Vite app (no SSR), so reading
  // window.location.search synchronously on render is safe.
  const embed =
    new URLSearchParams(window.location.search).get("embed") === "1";

  useEffect(() => {
    document.body.classList.add("constellation-page-body");
    return () => {
      document.body.classList.remove("constellation-page-body");
    };
  }, []);

  return (
    <div className="constellation-page">
      <CosmicLens embed={embed} />
      {!embed && (
        <div
          className="constellation-page__return"
          style={{ position: "absolute", bottom: 16, left: 16, zIndex: 10 }}
        >
          <a
            href="/"
            style={{
              color: "rgba(148, 163, 184, 0.7)",
              fontSize: 12,
              fontFamily: "ui-sans-serif, system-ui",
              textDecoration: "none",
            }}
          >
            ← return to the page
          </a>
        </div>
      )}
    </div>
  );
}

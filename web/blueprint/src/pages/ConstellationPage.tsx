/**
 * Standalone full-screen Constellation page.
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
import { Constellation } from "../components/Constellation";
import { useObservatory } from "../lib/useObservatory";

export function ConstellationPage() {
  // We just need the connection status + a no-op subscription so the EventSource
  // is open and feeding the Constellation's onEvent stream — the canvas itself
  // does its own subscription internally too, but exposing the status here keeps
  // the HUD honest.
  const { status } = useObservatory({ bufferSize: 1 });

  // The blueprint is a pure client-side Vite app (no SSR), so reading
  // window.location.search synchronously on render is safe. Avoid wrapping
  // in `typeof window !== "undefined"` — esbuild folds that branch to
  // false and the conditional below collapses, defeating the embed flag.
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
      <Constellation status={status} fullScreen />
      <div className="constellation-page__title">
        <div className="constellation-page__eyebrow">the substrate, running</div>
        {!embed && (
          <div className="constellation-page__return">
            <a href="/">← return to the page</a>
          </div>
        )}
      </div>
    </div>
  );
}

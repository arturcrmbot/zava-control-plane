// src/client/routes/Constellation.tsx
/**
 * Constellation route — embeds the blueprint app's full-screen Constellation
 * visual inside the Project Apex control plane via an iframe so operators
 * can flip between the dashboard view and the substrate-orbit visual without
 * leaving the control plane.
 *
 * URL resolution:
 *   - VITE_BLUEPRINT_URL set → use it verbatim (e.g. http://localhost:5175 in
 *     dev when running `npm run dev:blueprint` alongside `npm run dev:client`).
 *   - In dev (`import.meta.env.DEV`) and unset → default to
 *     http://${location.hostname}:5175 since the blueprint vite dev server
 *     conventionally lives there.
 *   - In production (single FastAPI container serving both) → same-origin "".
 *
 * The embed=1 query param tells ConstellationPage to suppress its
 * "← return to the page" link, which would otherwise navigate the iframe
 * away from the constellation.
 */

import { useMemo } from "react";

function resolveBlueprintBase(): string {
  // Vite injects VITE_*-prefixed env vars at build time.
  const fromEnv = (import.meta.env.VITE_BLUEPRINT_URL as string | undefined)?.trim();
  if (fromEnv) return fromEnv.replace(/\/$/, "");
  if (import.meta.env.DEV && typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:5175`;
  }
  return "";
}

export default function Constellation() {
  const src = useMemo(() => {
    const base = resolveBlueprintBase();
    return `${base}/?view=constellation&embed=1`;
  }, []);

  return (
    // Negative margin cancels the parent <main className="p-6">; height
    // matches the available main area (viewport minus 3rem header).
    <div className="-m-6 h-[calc(100vh-3rem)] bg-[#0a0a0c]">
      <iframe
        src={src}
        title="Substrate constellation"
        className="block w-full h-full border-0"
        allow="autoplay"
      />
    </div>
  );
}

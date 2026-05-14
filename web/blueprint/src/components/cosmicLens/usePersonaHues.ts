/**
 * usePersonaHues — fetch the persona-role → display_color map exposed by
 * `/api/personas/colors` (autonomous-domain-insights v1.1 F1) and cache it
 * in component state. Tiny payload (~30 entries), one HTTP call total.
 *
 * Used by FunctionPlanets to tint each persona-led function planet in its
 * persona's hue (Spec §9 polish item (e)) so the constellation visually
 * matches the DecisionTicker / drawer chip palette. Falls back silently
 * to an empty map on fetch failure — callers must apply their own
 * default hue when a role has no entry.
 */
import { useEffect, useState } from "react";

export type HueMap = Record<string, string>;

export function usePersonaHues(): HueMap {
  const [hues, setHues] = useState<HueMap>({});
  useEffect(() => {
    let cancelled = false;
    fetch("/api/personas/colors")
      .then((r) => (r.ok ? r.json() : {}))
      .then((d) => {
        if (cancelled || !d || typeof d !== "object") return;
        const clean: HueMap = {};
        for (const [role, hue] of Object.entries(d as Record<string, unknown>)) {
          if (typeof hue === "string" && hue) clean[role] = hue;
        }
        setHues(clean);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);
  return hues;
}

// web/client/hooks/useDensity.ts
//
// Card-density preference. Two modes:
//   - "cosy"    (default): the spacious layout with comfortable padding
//   - "compact":           tighter padding + smaller body text for power users
//
// We apply the resolved mode as a `density-cosy` / `density-compact` class
// on documentElement so the (small) set of compact-specific overrides in
// styles.css can target descendants without every card needing a prop.
import { useEffect } from "react";
import { useLocalStorageState } from "./useLocalStorageState";

export type DensityMode = "cosy" | "compact";

export function useDensity(): {
  density: DensityMode;
  setDensity: (m: DensityMode) => void;
  toggle: () => void;
} {
  const [density, setDensity] = useLocalStorageState<DensityMode>(
    "fleetctl.density", "cosy",
  );
  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove("density-cosy", "density-compact");
    root.classList.add(`density-${density}`);
  }, [density]);
  return {
    density,
    setDensity,
    toggle: () => setDensity(density === "compact" ? "cosy" : "compact"),
  };
}

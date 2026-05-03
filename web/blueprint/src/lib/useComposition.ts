import { useEffect, useState } from "react";
import type { CompositionTree } from "./types";

/**
 * Fetch the composition tree once on mount. Returns a tri-state:
 *   - data: tree | null
 *   - error: string | null
 *   - loading: boolean
 *
 * The page degrades gracefully when the API is unreachable — sections 4-6
 * render an "offline" message rather than blank space.
 */
export function useComposition() {
  const [data, setData] = useState<CompositionTree | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/blueprint/composition")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((tree: CompositionTree) => {
        if (cancelled) return;
        setData(tree);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { data, error, loading };
}

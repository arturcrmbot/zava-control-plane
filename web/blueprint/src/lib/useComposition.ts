import type { CompositionTree } from "./types";
import { COMPOSITION_FIXTURE } from "./composition.fixture";

// The article ships as a static bundle; the composition tree is
// captured once at build time from a running FastAPI control plane and
// served from the bundled fixture. To refresh, re-run the snapshot in
// composition.fixture.ts.
export function useComposition(): {
  data: CompositionTree;
  error: null;
  loading: false;
} {
  return { data: COMPOSITION_FIXTURE, error: null, loading: false };
}

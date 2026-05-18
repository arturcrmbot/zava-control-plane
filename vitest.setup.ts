// Test setup shared across vitest run.
// @testing-library/dom v10's waitFor only detects fake timers via the `jest`
// global. Aliasing vi as jest lets it recognize vitest fake timers and use the
// fake-timer code path instead of hanging on a real-timer microtask drain.
import { vi } from "vitest";

(globalThis as unknown as { jest?: typeof vi }).jest = vi;

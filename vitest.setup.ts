// Test setup shared across vitest run.
// @testing-library/dom v10's waitFor only detects fake timers via the `jest`
// global. Aliasing vi as jest lets it recognize vitest fake timers and use the
// fake-timer code path instead of hanging on a real-timer microtask drain.
import { vi } from "vitest";

(globalThis as unknown as { jest?: typeof vi }).jest = vi;

// jsdom doesn't ship an EventSource implementation. Components that
// open SSE connections (useSSE, DrawerReasoning, useFleetManagerStream)
// crash at mount in the test env without it. A no-op stub is enough —
// the tests don't actually exercise the stream contract; they just
// need the components to render.
class _NoopEventSource {
  readonly url: string;
  readonly readyState = 0;
  onopen: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  constructor(url: string) { this.url = url; }
  addEventListener(): void {}
  removeEventListener(): void {}
  close(): void {}
}
if (typeof (globalThis as { EventSource?: unknown }).EventSource === "undefined") {
  (globalThis as unknown as { EventSource: typeof _NoopEventSource }).EventSource = _NoopEventSource;
}

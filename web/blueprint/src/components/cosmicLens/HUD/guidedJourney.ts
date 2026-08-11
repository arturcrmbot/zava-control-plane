import type { ArcResult } from "./Narrator";

/**
 * Replay arc: six-phase explanatory Aurora journey over recorded telemetry.
 * No network mutation — this is guidance commentary, not a live trigger.
 */
const REPLAY_ARC: ArcResult = {
  phases: [
    {
      phase: "overrun",
      elapsed_ms: 0,
      summary: { brand: "BRAND-aurora" },
    },
    {
      phase: "cfo_observe",
      elapsed_ms: 7,
      headline: "Aurora at 123 % of FY budget — recommend freeze",
    },
    {
      phase: "approve",
      elapsed_ms: 5,
      policy_workflow_id: "WF-replay-001",
    },
    {
      phase: "cfo_observe_post",
      elapsed_ms: 8,
      headline: "Aurora dropped from proposals",
      freezes_remaining: 2,
    },
    {
      phase: "spawn_invoices",
      elapsed_ms: 26,
      cascades: [{ id: 1 }, { id: 2 }, { id: 3 }],
    },
    {
      phase: "ceo_synthesise",
      elapsed_ms: 2,
      headline: "Org-wide spend posture: 1 freeze active across 3 brands",
    },
  ],
  total_elapsed_ms: 48,
  narrative:
    "Recorded Aurora journey: budget overrun → CFO observed → freeze approved → cascade → CEO synthesis",
};

/**
 * Load the guided Aurora cross-functional journey.
 *
 * - Replay: returns the checked-in explanatory arc; no HTTP call.
 * - Live: POSTs the demo trigger and returns the parsed ArcResult.
 */
export async function loadGuidedJourney(isReplay: boolean): Promise<ArcResult> {
  if (isReplay) {
    return REPLAY_ARC;
  }

  const res = await fetch(
    "/api/demo/trigger/full-aurora-arc?delay_seconds=2.0&count=3",
    { method: "POST" },
  );
  if (!res.ok) {
    throw new Error(`Could not start the Aurora journey (${res.status})`);
  }
  return res.json() as Promise<ArcResult>;
}

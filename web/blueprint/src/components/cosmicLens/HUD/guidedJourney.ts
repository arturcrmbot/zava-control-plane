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
 *
 * The Aurora arc is agency-only (it needs `BRAND-aurora`). Under any other
 * vertical the trigger 404s, so fall back to the active actor world's own
 * hero scenario rather than surfacing a dead-end error to the viewer.
 */
export async function loadGuidedJourney(isReplay: boolean): Promise<ArcResult> {
  if (isReplay) {
    return REPLAY_ARC;
  }

  const res = await fetch(
    "/api/demo/trigger/full-aurora-arc?delay_seconds=2.0&count=3",
    { method: "POST" },
  );
  if (res.ok) {
    return res.json() as Promise<ArcResult>;
  }
  if (res.status === 404) {
    return loadActiveWorldJourney();
  }
  throw new Error(`Could not start the Aurora journey (${res.status})`);
}

interface SceneScenario {
  name: string;
  label?: string;
}

interface WorldScene {
  title?: string;
  scenarios?: SceneScenario[];
}

interface ScenarioRunResult {
  ok?: boolean;
  error?: string;
  workflow_id?: string;
  story_id?: string;
}

/**
 * Vertical-aware guided journey: trigger the active world's first hero
 * scenario and narrate the real ids it returns.
 */
async function loadActiveWorldJourney(): Promise<ArcResult> {
  const sceneRes = await fetch("/api/world/scene");
  if (!sceneRes.ok) {
    throw new Error(
      `No guided journey is available for this vertical (world scene ${sceneRes.status})`,
    );
  }
  const scene = (await sceneRes.json()) as WorldScene;
  const scenario = scene.scenarios?.[0];
  if (!scenario) {
    throw new Error("No guided journey is available for this vertical");
  }

  const started = Date.now();
  const runRes = await fetch(
    `/api/world/scenarios/${encodeURIComponent(scenario.name)}`,
    { method: "POST" },
  );
  if (!runRes.ok) {
    throw new Error(
      `Could not start ${scenario.label || scenario.name} (${runRes.status})`,
    );
  }
  const result = (await runRes.json()) as ScenarioRunResult;
  if (!result.ok) {
    throw new Error(result.error || "scenario rejected");
  }

  const label = scenario.label || scenario.name;
  return {
    phases: [
      {
        phase: "world_detected",
        elapsed_ms: Date.now() - started,
        headline: `${label} detected in ${scene.title || "the live world"}`,
      },
      {
        phase: "world_workflow",
        elapsed_ms: 0,
        headline: result.workflow_id
          ? `${result.workflow_id} opened — durable workflow now running`
          : "Durable workflow opened",
      },
      {
        phase: "world_decision",
        elapsed_ms: 0,
        headline:
          "Agents assemble the evidence; the accountable human still decides.",
      },
    ],
    total_elapsed_ms: Date.now() - started,
    narrative: `${label}: detected → durable workflow ${
      result.workflow_id || ""
    } → governed human decision`.trim(),
  };
}

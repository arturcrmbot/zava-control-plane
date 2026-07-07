// UI-shaped composition model. Mirrors the backend projection emitted on the
// `brief` stream event as `parsed` (see api/server/services/compose/brief_model.py)
// and the canonical fixture tests/api/compose/fixtures/capex_composition.json.

export type Lane = "automatic" | "analysis" | "human";
export type StepKind = "deterministic" | "agent" | "hitl";

export type EntityComp = {
  type: "entity";
  name: string;
  canonical: string;
  attributes: { k: string; v: string }[];
  relations: { kind: string; target: string }[];
};
export type SkillComp = { type: "skill"; name: string; phase: string };
export type ToolComp = { type: "tool"; name: string; system: string; operations: string[] };
export type PersonaComp = { type: "persona"; role: string; name: string; decisionPolicy: string };
export type AuthTier = { band: string; approver: string; cosign: string | null; escalatesIf: string | null };
export type AuthorityComp = {
  type: "authority";
  source: string;
  threshold: string;
  tiers: AuthTier[];
  chain: string[];
};
export type Component = EntityComp | SkillComp | ToolComp | PersonaComp | AuthorityComp;

export type Step = {
  id: string;
  name: string;
  kind: StepKind;
  lane: Lane;
  intent: string;
  components: Component[];
};

export type Composition = {
  title: string;
  workflowType: string;
  function: string;
  steps: Step[];
  entities: EntityComp[];
  ambient?: { name: string; trigger: string };
  counts: { steps: number; personae: number; skills: number; tools: number; entities: number; rules: number };
};

// ----- visual stage mapping ------------------------------------------------
// The agent reports fine-grained stages; the composer shows four milestones.
export type VisualStage = "read" | "design" | "build" | "ready";

export function visualStage(stage: string, done: boolean): VisualStage {
  if (done || stage === "ready") return "ready";
  if (stage === "composing" || stage === "graduating" || stage === "verifying") return "build";
  if (stage === "brief") return "design";
  return "read"; // intake | understanding | anything earlier
}

export const STAGE_ORDER: VisualStage[] = ["read", "design", "build", "ready"];

// A zoom target is either a step (by id) or a specific component within a step.
export type ZoomTarget =
  | { kind: "step"; stepId: string }
  | { kind: "component"; stepId: string; index: number };

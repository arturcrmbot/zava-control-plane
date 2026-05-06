/**
 * Shared types for the Constellation visualisation.
 *
 * The Constellation is one canvas: a luminous substrate sphere at the centre
 * (skills + MCP tools + validators), surrounded by an orbital ring of domain
 * orbs (one per workflow_type), with motes inside each orb representing
 * in-flight workflows.
 */

import type { CompositionTree } from "../types";

/** A single in-flight workflow rendered as a mote inside its domain orb. */
export interface Mote {
  /** Stable workflow_id from the event stream. */
  id: string;
  /** Last activity timestamp (ms epoch). Used for fading dead motes. */
  lastSeenMs: number;
  /** Which domain (workflow_type) this mote belongs to. */
  workflowType: string;
  /** 0..1 progress through the workflow (rough — derived from event count). */
  progress: number;
  /**
   * State machine for the mote:
   *   - alive       : routine progress through the workflow
   *   - awaiting    : suspended on a HITL gate (workflow.hitl.requested
   *                   or durable.suspended). Renders magenta with a slow
   *                   size-pulse so the operator can see "the bot stopped
   *                   and asked a human".
   *   - exception   : workflow.exception.detected or workflow.policy.violation
   *                   tripped — orange tint, faster pulse. Sticky until
   *                   resumed.
   *   - completed   : durable.workflow.completed / workflow.resolved —
   *                   bright flash then fade.
   *   - blocked     : durable.validator.blocked — red flash then fade.
   */
  state: "alive" | "awaiting" | "exception" | "completed" | "blocked";
  /** Set when an SLA proximity event has fired for this workflow. */
  slaBreach?: boolean;
  /** True if a HITL gate has been escalated (deeper magenta + faster pulse). */
  escalated?: boolean;
  /** Random per-mote orbit angle inside its parent orb. */
  seed: number;
  /** Most recent skill that fired for this workflow (label fodder). */
  lastSkill?: string | null;
  /** Most recent MCP tool that fired for this workflow. */
  lastTool?: string | null;
  /** Rolling tail of recent activity (newest first), capped at 6. */
  trail?: Array<{
    ts: number;
    label: string;
    kind: "skill" | "tool" | "validator";
  }>;
}

/** A pulse: a substrate dot that just brightened because its skill/tool fired. */
export interface Pulse {
  /** Index into the substrate dot array. */
  dotIdx: number;
  /** Time the pulse started (ms epoch). */
  startMs: number;
  /**
   * What kind of dot this is — drives the pulse colour:
   *   - "skill"     → amber (matches the resting warm tint, brightened)
   *   - "tool"      → cool blue (matches resting cool tint, brightened)
   *   - "validator" → red (the validator-blocked alarm colour)
   */
  kind: "skill" | "tool" | "validator";
}

/**
 * Manifest of which substrate dot belongs to which skill / MCP tool /
 * validator. Built once at mount time from the composition tree.
 */
export interface SubstrateMap {
  /** Total number of dots on the sphere. */
  total: number;
  /** Skill name → dot index. */
  skillIdx: Map<string, number>;
  /** MCP tool name → dot index. */
  toolIdx: Map<string, number>;
  /** Validator name → dot index. (We bucket validators with skills for now.) */
  validatorIdx: Map<string, number>;
  /** For each dot, its category — used for resting colour tint. */
  category: Uint8Array; // 0 = filler, 1 = skill, 2 = tool, 3 = validator
}

/**
 * Layout for the orbiting domain orbs. Computed once from the composition
 * tree's live domains.
 */
export interface DomainOrbDescriptor {
  workflowType: string;
  displayName: string;
  /** Angle on the orbit ring, in radians. Stable across re-renders. */
  angle: number;
}

/** Build the orbit descriptors from the composition tree's live domains. */
export function describeDomainOrbits(
  composition: CompositionTree | null,
): DomainOrbDescriptor[] {
  if (!composition) return [];
  const live = composition.domains.filter(
    (d) => d.status === "live" && d.workflow_type,
  );
  // Stable angular ordering — sort by name for determinism.
  const sorted = [...live].sort((a, b) => a.name.localeCompare(b.name));
  return sorted.map((d, i) => ({
    workflowType: d.workflow_type as string,
    displayName: d.name,
    angle: (i * 2 * Math.PI) / sorted.length - Math.PI / 2,
  }));
}

/**
 * The Org Building (IP4) — translate ObservatoryEvent → AnimEntry.
 *
 * Pure: takes an event, the function-by-workflow-type lookup, and the
 * function registry; returns the AnimEntry to enqueue (or null if we
 * don't know how to render it / required positions are unknown).
 *
 * Spec §4 colour palette:
 *   decisions    = violet  #a78bfa
 *   entity flows = cyan    #06b6d4
 *   ambient      = amber   #fbbf24
 *   cadence      = white pulse
 *   sub-spawn    = magenta #ec4899
 *   x-fn beams   = teal    #14b8a6
 */
import type { AnimEntry } from "./animationQueue";
import { nextAnimId } from "./animationQueue";
import {
  ambientSensorPosition,
  floorFrontCentre,
  lobbyKindPosition,
  windowPosition,
} from "./floorLayout";
import type { OrgFunction } from "./useOrgData";
import type { LayerFlags } from "./layerToggles";
import type { ObservatoryEvent } from "./types";

export const COLORS = {
  decision: "#a78bfa",
  entity: "#06b6d4",
  ambient: "#fbbf24",
  cadence: "#ffffff",
  subspawn: "#ec4899",
  beam: "#14b8a6",
} as const;

export interface EventCtx {
  /** workflow_type → function key (built from functions[].owns_domains[]). */
  functionByWorkflowType: Map<string, string>;
  /** function key → OrgFunction (for ambient agent index lookup). */
  functionByName: Map<string, OrgFunction>;
  layers: LayerFlags;
}

/** workflow_id prefix → workflow_type. Mirrors the per-domain
 *  `workflow_id_prefix` in api/shared/domains.py. Used as a fallback
 *  when the SSE event doesn't carry workflow_type explicitly (most
 *  durable / entity events don't). */
export const PREFIX_TO_WORKFLOW_TYPE: Record<string, string> = {
  EXP: "expense-claim",
  HIRE: "hiring",
  TRV: "travel-preapproval",
  TRVL: "travel-preapproval",
  VKY: "vendor-kyc",
  ONB: "employee-onboarding",
  ITAR: "it-access-request",
  CRN: "contract-renewal",
  PRR: "perf-review",
  API: "ap-invoice",
  POW: "purchase-order",
  CRW: "contract-review",
  DPI: "privacy-dpia",
  TFX: "treasury-fx",
  CMP: "creative-campaign",
  H2P: "hire-to-productive",
  VRP: "vendor-risk-to-pay",
  L2C: "lead-to-cash",
  FYC: "fy-close",
  BRD: "board-prep",
};

/** Extract the {prefix} from an "{prefix}-NNNN" workflow id. */
function prefixOf(workflowId: string | null | undefined): string | null {
  if (!workflowId) return null;
  const m = workflowId.match(/^([A-Z]+)-/);
  return m ? m[1] : null;
}

/** Resolve which function "fired" the event. Falls back through:
 *  1. explicit event.function
 *  2. workflow_type lookup
 *  3. domain lookup (owns_domains may include the raw domain name)
 *  4. workflow_id prefix → workflow_type → function (entity / durable
 *     events don't carry workflow_type but always carry workflow_id)
 */
export function resolveFunction(
  event: ObservatoryEvent,
  ctx: EventCtx,
): string | null {
  if (event.function) return event.function;
  const wt = event.workflow_type ?? null;
  if (wt && ctx.functionByWorkflowType.has(wt)) {
    return ctx.functionByWorkflowType.get(wt)!;
  }
  if (event.domain && ctx.functionByWorkflowType.has(event.domain)) {
    return ctx.functionByWorkflowType.get(event.domain)!;
  }
  const prefix = prefixOf(event.workflow_id);
  if (prefix) {
    const inferredWt = PREFIX_TO_WORKFLOW_TYPE[prefix];
    if (inferredWt && ctx.functionByWorkflowType.has(inferredWt)) {
      return ctx.functionByWorkflowType.get(inferredWt)!;
    }
  }
  return null;
}

/** Translate a single event into an AnimEntry, honouring layer flags.
 *  Returns null when the event isn't visualised or required data is
 *  missing. */
export function translateEvent(
  event: ObservatoryEvent,
  ctx: EventCtx,
): AnimEntry | null {
  const fn = resolveFunction(event, ctx);
  const isPenthouse = fn === "ceo";

  switch (event.type) {
    case "entity.upserted": {
      if (!ctx.layers.entityFlows) return null;
      if (!fn) return null;
      const from = windowPosition(fn, event.workflow_id, isPenthouse);
      const kind = event.entity_kind ?? "Person";
      const to = lobbyKindPosition(kind);
      if (!from || !to) return null;
      return {
        id: nextAnimId("mote"),
        kind: "mote",
        from,
        to,
        color: COLORS.entity,
        t: 0,
        lifetime: 1.6,
        payload: { kind, entityId: event.entity_id ?? null },
      };
    }
    case "decision.recorded": {
      if (!ctx.layers.decisionSparks) return null;
      if (!fn) return null;
      const from = windowPosition(fn, event.workflow_id, isPenthouse);
      const to = lobbyKindPosition("Decision");
      if (!from || !to) return null;
      return {
        id: nextAnimId("spark"),
        kind: "spark",
        from,
        to,
        color: COLORS.decision,
        t: 0,
        lifetime: 1.4,
        payload: {
          decisionId: event.decision_id ?? event.entity_id ?? null,
          gate: event.gate ?? null,
        },
      };
    }
    case "ambient.decided": {
      if (!ctx.layers.ambientFlashes) return null;
      if (!fn) return null;
      const fnDef = ctx.functionByName.get(fn);
      const agents = fnDef?.ambientAgents ?? [];
      const idx = event.ambient_agent ? agents.indexOf(event.ambient_agent) : 0;
      const safeIdx = idx < 0 ? 0 : idx;
      const from =
        ambientSensorPosition(fn, safeIdx, Math.max(1, agents.length)) ??
        floorFrontCentre(fn);
      if (!from) return null;
      return {
        id: nextAnimId("ambient"),
        kind: "pulse",
        from,
        color: COLORS.ambient,
        t: 0,
        lifetime: 1.0,
        payload: { ambient: event.ambient_agent ?? null, scope: "ambient" },
      };
    }
    case "cadence.tick": {
      if (!ctx.layers.cadencePulses) return null;
      if (!fn) {
        // Cadence ticks may not name a function — render as a generic
        // building-wide white flash anchored at floor 0 centre.
        return {
          id: nextAnimId("cadence"),
          kind: "pulse",
          from: [0, 1.0, 1.1],
          color: COLORS.cadence,
          t: 0,
          lifetime: 0.9,
          payload: { cadence: event.cadence_name ?? null, scope: "cadence" },
        };
      }
      const fnDef = ctx.functionByName.get(fn);
      const agents = fnDef?.ambientAgents ?? [];
      const from =
        ambientSensorPosition(fn, 0, Math.max(1, agents.length)) ??
        floorFrontCentre(fn);
      if (!from) return null;
      return {
        id: nextAnimId("cadence"),
        kind: "pulse",
        from,
        color: COLORS.cadence,
        t: 0,
        lifetime: 0.9,
        payload: { cadence: event.cadence_name ?? null, scope: "cadence" },
      };
    }
    case "workflow.completed":
    case "durable.workflow.completed":
    case "workflow.resolved": {
      if (!ctx.layers.activityHeat) return null;
      if (!fn) return null;
      const from = windowPosition(fn, event.workflow_id, isPenthouse);
      if (!from) return null;
      return {
        id: nextAnimId("wfdone"),
        kind: "pulse",
        from,
        color: "#cfd2d6",
        t: 0,
        lifetime: 1.2,
        payload: { scope: "window-pulse" },
      };
    }
    case "workflow.sub_spawned": {
      if (!ctx.layers.activityHeat) return null;
      // Need a parent + child function. If we can't resolve both we
      // skip — the meta-workflow visual relies on knowing both ends.
      const parentFn = fn;
      const childWt = (event as ObservatoryEvent & { child_workflow_type?: string | null })
        .child_workflow_type;
      const childFn =
        (childWt && ctx.functionByWorkflowType.get(childWt)) ?? parentFn;
      if (!parentFn || !childFn) return null;
      const from = windowPosition(
        parentFn,
        event.parent_workflow_id ?? event.workflow_id,
        parentFn === "ceo",
      );
      const to = windowPosition(
        childFn,
        event.child_workflow_id ?? null,
        childFn === "ceo",
      );
      if (!from || !to) return null;
      return {
        id: nextAnimId("filament"),
        kind: "filament",
        from,
        to,
        color: COLORS.subspawn,
        t: 0,
        lifetime: 1.8,
        payload: { parentFn, childFn },
      };
    }
    default:
      return null;
  }
}

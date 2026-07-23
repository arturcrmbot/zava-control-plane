/**
 * Cosmic Lens v2 — Action label generator.
 *
 * Translates raw SSE/poll events into one-line human-readable labels
 * shown above parked rockets.
 *
 * Two modes:
 *   - Capabilities: PURPOSE — "what is the rocket here to do"
 *     e.g. "awaiting HITL decision (ap_clerk)" / "running stripe.charge"
 *   - Entities: OPERATION — "what is the rocket doing to data"
 *     e.g. "reading person details (CAND-0042)" / "updating invoice INV-0871"
 *
 * All wording flows through `humanizeLabel` / `prettyActor` from
 * `@shared/humanize` so unknown ids still render as Title Case English —
 * we never let a raw `executor.*` / `entity.*` / `tool.*` / `workflow.*` /
 * `persona.*` event type leak into the UI.
 */

import { humanizeLabel, prettyActor, titleCase } from "../../../../../shared/humanize";

export interface RocketEvent {
  type: string;
  workflow_id?: string;
  persona?: string;
  agent_name?: string;
  tool_name?: string;
  entity_kind?: string;
  entity_id?: string;
  verb?: string;
  reason?: string;
  phase_name?: string;
  decision_id?: string;
}

export function labelForCapability(ev: RocketEvent): string {
  switch (ev.type) {
    case "persona.thinking":
      return `${prettyActor(ev.persona ?? "human")} is reviewing`;
    case "persona.decided":
      return `${prettyActor(ev.persona ?? "human")} decided`;
    case "tool.invoked": {
      const name = ev.tool_name ?? ev.agent_name ?? "tool";
      return `Running ${titleCase(name)}`;
    }
    case "tool.completed": {
      const name = ev.tool_name ?? ev.agent_name ?? "tool";
      return `${titleCase(name)} — done`;
    }
    case "ambient.decided":
      return `${prettyActor(ev.agent_name ?? "agent")} reasoned`;
    case "decision.recorded":
      return `Decision recorded`;
    case "workflow.sub_spawned":
      return `Spawned a sub-workflow`;
    default:
      return ev.type ? humanizeLabel(ev.type).text : "Activity";
  }
}

export function labelForEntity(ev: RocketEvent): string {
  const kind = ev.entity_kind ?? "entity";
  // Drop "-unknown" suffix and similar placeholder noise
  const cleanId = (ev.entity_id ?? "").replace(/-unknown$/i, "").replace(/^.*-unknown-/, "");
  const id = cleanId && !cleanId.endsWith("-unknown") ? ` ${cleanId}` : "";
  switch (ev.type) {
    case "entity.read":
      return `Looked up ${kindToVerb(kind)}${id}`;
    case "entity.upserted":
      return `${ev.verb === "create" ? "Created" : "Updated"} ${kindToVerb(kind)}${id}`;
    case "entity.linked":
      return `Connected ${kindToVerb(kind)}${id}`;
    case "entity.write.failed":
      return `Couldn't save ${kindToVerb(kind)}${id}`;
    case "entity.write.killed":
      return `Save blocked: ${kindToVerb(kind)}${id}`;
    default:
      return ev.type ? humanizeLabel(ev.type).text : "Activity";
  }
}

/** Determine read vs write from event type. Used for directional beam. */
export function isWriteEvent(type: string): boolean {
  return (
    type === "entity.upserted" ||
    type === "entity.linked" ||
    type === "entity.write.failed" ||
    type === "entity.write.killed"
  );
}

export function isReadEvent(type: string): boolean {
  return type === "entity.read";
}

function kindToVerb(kind: string): string {
  // "Vendor" → "vendor record"
  // "Person" → "person details"
  // "Decision" → "decision"
  switch (kind) {
    case "Person":
      return "person details";
    case "Vendor":
      return "vendor record";
    case "Invoice":
      return "invoice";
    case "Candidate":
      return "candidate";
    case "Job":
      return "job posting";
    case "Offer":
      return "offer";
    case "Contract":
      return "contract";
    case "Decision":
      return "decision";
    case "Document":
      return "document";
    case "Account":
      return "account";
    case "Payment":
      return "payment";
    case "PerformanceReview":
      return "perf review";
    default:
      return kind.toLowerCase();
  }
}

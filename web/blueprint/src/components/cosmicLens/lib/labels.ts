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
 */

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
      return `awaiting HITL decision (${ev.persona ?? "human"})`;
    case "persona.decided":
      return `${ev.persona ?? "human"} decided`;
    case "tool.invoked": {
      const name = ev.tool_name ?? ev.agent_name ?? "tool";
      return `running ${name}`;
    }
    case "tool.completed": {
      const name = ev.tool_name ?? ev.agent_name ?? "tool";
      return `${name} done`;
    }
    case "ambient.decided":
      return `${ev.agent_name ?? "agent"} reasoning`;
    case "decision.recorded":
      return `decision recorded`;
    case "workflow.sub_spawned":
      return `spawning sub-workflow`;
    default:
      return ev.type;
  }
}

export function labelForEntity(ev: RocketEvent): string {
  const kind = ev.entity_kind ?? "entity";
  // Drop "-unknown" suffix and similar placeholder noise
  const cleanId = (ev.entity_id ?? "").replace(/-unknown$/i, "").replace(/^.*-unknown-/, "");
  const id = cleanId && !cleanId.endsWith("-unknown") ? ` ${cleanId}` : "";
  switch (ev.type) {
    case "entity.read":
      return `reading ${kindToVerb(kind)}${id}`;
    case "entity.upserted":
      return `${ev.verb === "create" ? "creating" : "updating"} ${kindToVerb(kind)}${id}`;
    case "entity.linked":
      return `linking ${kindToVerb(kind)}${id}`;
    case "entity.write.failed":
      return `failed to write ${kindToVerb(kind)}${id}`;
    case "entity.write.killed":
      return `write blocked: ${kindToVerb(kind)}${id}`;
    default:
      return ev.type;
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

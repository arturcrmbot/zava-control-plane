export interface GuidedJourney {
  workflowId: string;
  source: "live" | "replay";
}

export interface JourneyDetails {
  workflowId: string;
  workflowType: string;
  status: string;
  currentPhase: string;
  outcome?: string;
  reason?: string;
  phases: { name: string; status: string }[];
  activeExceptionId?: string;
  recommendation?: string;
  policyDecisionId?: string;
  children: { workflowId: string; status?: string }[];
}

const AURORA_TYPE = "aurora-budget-response";

function record(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : undefined;
}

function text(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function requiredText(value: unknown, field: string): string {
  const result = text(value);
  if (!result) throw new Error(`Workflow evidence is missing ${field}`);
  return result;
}

async function responseBody(response: Response, label: string): Promise<unknown> {
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const rawDetail = record(body)?.detail;
    const detail = text(rawDetail) || text(record(rawDetail)?.message);
    throw new Error(detail || `${label} (${response.status})`);
  }
  return response.json();
}

/** Follow a real existing run; create one only when live has no Aurora run. */
export async function loadGuidedJourney(
  isReplay: boolean, requestId?: string,
): Promise<GuidedJourney> {
  const body = await responseBody(await fetch("/api/workflows"), "Could not load workflows");
  if (!Array.isArray(body)) throw new Error("Workflow index is not a list");
  const roots = body
    .map(record)
    .filter((item): item is Record<string, unknown> => !!item &&
      item.type === AURORA_TYPE && !!text(item.id) &&
      !!text(item.orchestrationInstanceId ?? item.orchestration_instance_id))
    .sort((a, b) => Number(a.createdAt ?? a.created_at ?? 0) - Number(b.createdAt ?? b.created_at ?? 0));
  const latest = roots[roots.length - 1];
  if (latest) {
    return {
      workflowId: requiredText(latest.id, "workflow id"),
      source: isReplay ? "replay" : "live",
    };
  }
  if (isReplay) throw new Error("No recorded Aurora execution is available in this tape.");
  return startAuroraJourney(requestId);
}

export async function startAuroraJourney(
  requestId: string = crypto.randomUUID(),
): Promise<GuidedJourney> {
  const response = await fetch("/api/demo/trigger/full-aurora-arc?count=3", {
    method: "POST",
    headers: { "Idempotency-Key": requestId },
  });
  if (response.status === 404) return startActiveWorldJourney();
  const body = record(await responseBody(response, "Could not start Aurora"));
  if (response.status !== 202) {
    throw new Error("Expected a Durable workflow acceptance (202), not a caption script.");
  }
  return {
    workflowId: requiredText(body?.workflow_id, "accepted workflow id"),
    source: "live",
  };
}

async function startActiveWorldJourney(): Promise<GuidedJourney> {
  const scene = record(await responseBody(
    await fetch("/api/world/scene"), "Could not load the active world",
  ));
  const scenario = Array.isArray(scene?.scenarios) ? record(scene.scenarios[0]) : undefined;
  const name = text(scenario?.name);
  if (!name) throw new Error("No guided journey is available for this vertical.");
  const result = record(await responseBody(
    await fetch(`/api/world/scenarios/${encodeURIComponent(name)}`, { method: "POST" }),
    "Could not start the active world scenario",
  ));
  if (result?.ok !== true) throw new Error(text(result?.error) || "Scenario was not accepted.");
  const workflowId = text(result.workflow_id);
  if (!workflowId) {
    throw new Error("Scenario accepted, but no workflow evidence ID was returned. Inspect the world view.");
  }
  return { workflowId, source: "live" };
}

export async function readJourneyDetails(workflowId: string): Promise<JourneyDetails | null> {
  const response = await fetch(`/api/workflows/${encodeURIComponent(workflowId)}`);
  if (response.status === 404) return null;
  const body = record(await responseBody(response, "Could not load workflow evidence"));
  const workflow = record(body?.workflow);
  if (workflow?.id !== workflowId) throw new Error("Workflow evidence identity does not match the selected run.");
  if (!Array.isArray(body?.phases)) throw new Error("Workflow evidence has no phase list.");

  const pack = record(body.packDetail);
  const outputs = record(pack?.outputs);
  const recommendation = record(outputs?.recommendation);
  const policy = record(outputs?.policy);
  const exception = record(body.activeException);
  const metadata = record(workflow.metadata);
  const children = Array.isArray(pack?.children) ? pack.children : [];
  return {
    workflowId,
    workflowType: requiredText(workflow.type, "workflow type"),
    status: requiredText(workflow.status, "workflow status"),
    currentPhase: text(workflow.currentPhase ?? workflow.current_phase) || "",
    outcome: text(metadata?.outcome) || (metadata?.rejected === true ? "rejected" : undefined),
    reason: text(metadata?.rejection_reason) || text(metadata?.failure_reason),
    phases: body.phases.map((value) => {
      const phase = record(value);
      return {
        name: requiredText(phase?.name, "phase name"),
        status: requiredText(phase?.status, "phase status"),
      };
    }),
    activeExceptionId: text(exception?.id),
    recommendation: text(recommendation?.rationale),
    policyDecisionId: text(policy?.decision_id),
    children: children.map((value) => {
      const child = record(value);
      return {
        workflowId: requiredText(child?.workflow_id ?? value, "child workflow id"),
        status: text(record(child?.outcome)?.status),
      };
    }),
  };
}

export async function resolveJourneyDecision(
  exceptionId: string, resolution: "approve" | "reject",
): Promise<void> {
  const response = await fetch(`/api/exceptions/${encodeURIComponent(exceptionId)}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resolution }),
  });
  const body = record(await responseBody(response, "Could not submit the decision"));
  if (body?.resolved !== 1) throw new Error("The decision was not acknowledged.");
}

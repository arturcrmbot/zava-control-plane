// web/shared/feedItems.ts
//
// FeedItem is the normalised, ordered unit the <Feed> renders. Each card
// type in the feed corresponds to one variant of this discriminated union.
// Builders take the existing hook outputs (Workflow[], Exception[], etc.)
// and project them into FeedItem[] without mutating their source.

import type { Workflow, Exception, Severity } from "./types";
import type { CardType } from "./roles";

export interface FeedItemBase {
  id: string;             // stable: "<type>:<source-id>"
  type: CardType;
  timestamp: number;      // seconds since epoch; used for chronological sort
  workflowId?: string;
  domain?: string;        // workflow.type, used by domain-chip filtering
  severity?: Severity | null;
}

export interface HITLItem extends FeedItemBase {
  type: "hitl";
  workflowId: string;
  workflow?: Workflow;    // attached for renderer; optional for serialisation
}

export interface ExceptionItem extends FeedItemBase {
  type: "exception";
  exception: Exception;
  workflow?: Workflow;
}

export interface ExternalWaitItem extends FeedItemBase {
  type: "external-wait";
  workflowId: string;
  workflow: Workflow;
  awaitingReason?: string;
}

export interface MilestoneItem extends FeedItemBase {
  type: "milestone";
  workflowId: string;
  workflow: Workflow;
  outcome: "completed" | "failed";
}

export interface PolicyItem extends FeedItemBase {
  type: "policy";
  policyId: string;
  description: string;
  previousValue?: unknown;
  currentValue: unknown;
  actor?: string;
}

export interface AgentEventItem extends FeedItemBase {
  type: "agent-event";
  source: "fleet-manager" | "orchestration";
  kind: string;
  data: unknown;
}

export interface ResolvedItem extends FeedItemBase {
  type: "resolved";
  // The original card it replaced; preserved so the Resolved card can
  // re-render the receipt thumb / summary in collapsed form.
  origin: HITLItem | ExceptionItem | ExternalWaitItem;
  verb: string;           // "Approved" | "Rejected" | ...
  actor: string;          // "you" | "agent" | ...
  actedAt: number;
}

export type FeedItem =
  | HITLItem
  | ExceptionItem
  | ExternalWaitItem
  | MilestoneItem
  | PolicyItem
  | AgentEventItem
  | ResolvedItem;

// ---------- builders ----------

export function buildHITLCards(workflows: Workflow[]): HITLItem[] {
  return workflows
    .filter((w) => w.status === "awaiting_hitl")
    .map((w) => ({
      id: `hitl:${w.id}`,
      type: "hitl",
      timestamp: w.createdAt,
      workflowId: w.id,
      domain: w.type,
      severity: w.activeExceptionId ? "high" : "medium",
      workflow: w,
    }));
}

export function buildExceptionCards(
  exceptions: Exception[],
  workflows: Workflow[] = [],
): ExceptionItem[] {
  const byId = new Map(workflows.map((w) => [w.id, w]));
  return exceptions
    .filter((e) => !e.resolvedAt)
    .map((e) => ({
      id: `exception:${e.id}`,
      type: "exception",
      timestamp: e.createdAt,
      workflowId: e.workflowId,
      severity: e.severity,
      exception: e,
      workflow: byId.get(e.workflowId),
    }));
}

export function buildExternalWaitCards(workflows: Workflow[]): ExternalWaitItem[] {
  return workflows
    .filter((w) => {
      const meta = (w.metadata ?? {}) as { wait_kind?: string };
      return meta.wait_kind === "external_party";
    })
    .map((w) => ({
      id: `external-wait:${w.id}`,
      type: "external-wait",
      timestamp: w.createdAt,
      workflowId: w.id,
      domain: w.type,
      severity: "medium",
      workflow: w,
      awaitingReason: ((w.metadata ?? {}) as { awaiting_reason?: string }).awaiting_reason,
    }));
}

export function buildMilestoneCards(workflows: Workflow[]): MilestoneItem[] {
  return workflows
    .filter((w) => w.status === "completed" || w.status === "failed")
    .map((w) => ({
      id: `milestone:${w.id}`,
      type: "milestone",
      timestamp: w.createdAt,
      workflowId: w.id,
      domain: w.type,
      severity: w.status === "failed" ? "high" : null,
      workflow: w,
      outcome: w.status as "completed" | "failed",
    }));
}

export interface PolicySnapshot {
  id: string;
  description: string;
  currentValue: number | string | boolean;
  gitSha?: string;
  author?: string;
  updatedAt?: number;
}

export function buildPolicyCards(events: PolicySnapshot[]): PolicyItem[] {
  return events.map((p) => ({
    id: `policy:${p.id}:${p.gitSha ?? "_"}`,
    type: "policy",
    timestamp: p.updatedAt ?? 0,
    policyId: p.id,
    severity: null,
    description: p.description,
    currentValue: p.currentValue,
    actor: p.author,
  }));
}

// NOTE: Unit mismatch is intentional. Fleet-Manager events (`useFleetManagerStream`)
// and Orchestration events (`useOrchestrationStream`) expose `timestamp` in
// **milliseconds since epoch** — that is the native shape from the underlying
// SSE event bus. Every other builder in this module uses seconds. The conversion
// is done once inside `buildAgentEventCards` (`Math.floor(e.timestamp / 1000)`),
// so consumers of FeedItem can rely on every item's `timestamp` being in seconds.
//
// `data` is the Fleet-Manager event payload; `payload` is the Orchestration event
// payload. The builder normalises both into `AgentEventItem.data`.
export interface AgentEventLike {
  kind: string;
  timestamp: number;  // milliseconds since epoch
  workflow_id?: string;
  data?: unknown;
  payload?: unknown;
}

export function buildAgentEventCards(
  fmEvents: AgentEventLike[],
  orchEvents: AgentEventLike[],
): AgentEventItem[] {
  const fm: AgentEventItem[] = fmEvents.map((e, i) => ({
    id: `agent-event:fm:${e.timestamp}:${i}`,
    type: "agent-event",
    timestamp: Math.floor(e.timestamp / 1000),
    severity: e.kind === "error" ? "high" : null,
    source: "fleet-manager",
    kind: e.kind,
    data: e.data,
    workflowId: typeof (e.data as { workflow_id?: string } | undefined)?.workflow_id === "string"
      ? (e.data as { workflow_id: string }).workflow_id
      : undefined,
  }));
  const orch: AgentEventItem[] = orchEvents.map((e, i) => ({
    id: `agent-event:orch:${e.timestamp}:${i}`,
    type: "agent-event",
    timestamp: Math.floor(e.timestamp / 1000),
    severity: e.kind.endsWith(".failed") ? "high" : null,
    source: "orchestration",
    kind: e.kind,
    data: e.payload,
    workflowId: e.workflow_id,
  }));
  return [...fm, ...orch];
}

export function chronological(items: FeedItem[]): FeedItem[] {
  return [...items].sort((a, b) => b.timestamp - a.timestamp);
}

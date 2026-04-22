// control-plane/src/shared/events.ts
import type { OtelSpan, PhaseName, Severity, ExceptionCategory } from "./types";

export type FleetEvent =
  | { type: "workflow.started"; workflowId: string }
  | { type: "workflow.phase.started"; workflowId: string; phase: PhaseName }
  | { type: "workflow.phase.completed"; workflowId: string; phase: PhaseName; durationMs: number }
  | { type: "workflow.phase.failed"; workflowId: string; phase: PhaseName; reason: string }
  | { type: "workflow.exception.detected"; workflowId: string; category: ExceptionCategory; severity: Severity }
  | { type: "workflow.hitl.requested"; workflowId: string; reason: string }
  | { type: "workflow.sla.breach_imminent"; workflowId: string; minutesRemaining: number }
  | { type: "workflow.policy.violation"; workflowId: string; policyId: string }
  | { type: "workflow.resolved"; workflowId: string; resolution: string }
  | { type: "otel.span.emitted"; span: OtelSpan }
  | { type: "fleet.anomaly.detected"; pattern: string; workflowIds: string[] }
  | { type: "fleet.tick"; timestamp: number }
  | { type: "fleet.overload"; queueDepth: number };

export type FleetEventType = FleetEvent["type"];

export const WAKE_TYPES: ReadonlySet<FleetEventType> = new Set([
  "workflow.exception.detected",
  "workflow.hitl.requested",
  "workflow.sla.breach_imminent",
  "workflow.policy.violation",
  "fleet.anomaly.detected",
  "fleet.tick"
]);

export function wakesFleetManager(e: FleetEvent): boolean {
  return WAKE_TYPES.has(e.type);
}

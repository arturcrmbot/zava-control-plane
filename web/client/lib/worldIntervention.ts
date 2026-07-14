// Shared causal derivation for support and telco intervention strips.
// Callers append their scenario-specific tail steps.
import type { WorldEvent } from "@client/hooks/useWorldSimulation";

export interface InterventionStep {
  label: string;
  eventId: string;
  detail?: string;
}

export interface CommonIntervention {
  trace: string;
  traceEvents: WorldEvent[];
  steps: InterventionStep[];
}

export interface DeriveCommonInterventionOptions {
  pressureLabel?: string;
  pressureDetail?: (event: WorldEvent) => string | undefined;
}

/** Derive common causal steps for the newest matching trace. */
export function deriveCommonIntervention(
  events: WorldEvent[],
  isTraceTrigger: (event: WorldEvent) => boolean,
  options: DeriveCommonInterventionOptions = {},
): CommonIntervention | null {
  let trace: string | null = null;
  for (const e of events) {
    if (isTraceTrigger(e)) trace = e.trace_id;
  }
  if (!trace) return null;

  const traceEvents = events.filter((e) => e.trace_id === trace);
  const find = (type: string) => traceEvents.find((e) => e.type === type);
  const steps: InterventionStep[] = [];

  const pressure = find("sensor.tripped");
  if (pressure) {
    steps.push({
      label: options.pressureLabel ?? "Pressure detected",
      eventId: pressure.event_id,
      detail: options.pressureDetail?.(pressure),
    });
  }

  const requested = find("responder.requested");
  if (requested) steps.push({ label: "Responder requested", eventId: requested.event_id });

  const decided = find("responder.decided");
  const deferred = find("responder.deferred");
  const failed = find("responder.failed");
  if (decided) {
    const instance = String((decided.payload?.instance_id as string) ?? "");
    steps.push({ label: "Durable decided", eventId: decided.event_id, detail: instance.slice(0, 12) || undefined });
  } else if (deferred) {
    steps.push({ label: "Durable deferred", eventId: deferred.event_id });
  } else if (failed) {
    steps.push({ label: "Responder failed", eventId: failed.event_id });
  }

  const accepted = find("command.accepted");
  if (accepted) steps.push({ label: "Command accepted", eventId: accepted.event_id });

  return { trace, traceEvents, steps };
}

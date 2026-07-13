// web/client/lib/worldIntervention.ts
//
// Shared causal derivation for the /world "Durable intervention" strip.
// Both World.tsx (ticket-queue scenario) and TelcoWorld.tsx (network
// scenario) walk the same first stretch of a Durable trace — a tripped
// sensor, a responder request, its decided/deferred/failed outcome, and the
// resulting command.accepted — before appending their own scenario-specific
// tail (worker.reallocated vs session.rerouted + site.recovered). This module
// owns only that common stretch; it is a pure function, not a component or
// command/sensor framework.
import type { WorldEvent } from "@client/hooks/useWorldSimulation";

export interface InterventionStep {
  label: string;
  eventId: string;
  detail?: string;
}

export interface CommonIntervention {
  trace: string;
  /** All events on this trace, for the caller to derive its own tail steps. */
  traceEvents: WorldEvent[];
  steps: InterventionStep[];
}

export interface DeriveCommonInterventionOptions {
  /** Step label for the sensor.tripped step. Defaults to "Pressure detected". */
  pressureLabel?: string;
  /** Optional detail extracted from the sensor.tripped event's payload. */
  pressureDetail?: (event: WorldEvent) => string | undefined;
}

/**
 * Finds the most recent trace matched by `isTraceTrigger` and derives the
 * common causal steps (sensor.tripped, responder.requested,
 * responder.decided|deferred|failed, command.accepted) for it. Returns null
 * if no matching trace is found. Callers append scenario-specific tail steps
 * to the returned `steps` array using `traceEvents`.
 */
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

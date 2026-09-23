import { describe, it, expect } from "vitest";
import { pulseKindForFlash } from "../PlanetCompletions";

describe("pulseKindForFlash", () => {
  it("rings a planet when one of its workflows completes", () => {
    expect(pulseKindForFlash({ type: "workflow.completed", ts: 0 })).toBe("completion");
    expect(pulseKindForFlash({ type: "durable.workflow.completed", ts: 0 })).toBe("completion");
  });

  it("gives routine world activity a heartbeat, not a completion ring", () => {
    expect(
      pulseKindForFlash({ type: "world.activity", ts: 0, function: "payments", world_type: "banking.payment.settled" }),
    ).toBe("heartbeat");
  });

  it("raises an alarm when the world trips a sensor", () => {
    expect(
      pulseKindForFlash({ type: "world.activity", ts: 0, function: "retail-banking", world_type: "sensor.tripped" }),
    ).toBe("alarm");
  });

  it("ignores everything else", () => {
    expect(pulseKindForFlash({ type: "persona.decided", ts: 0 })).toBeNull();
  });
});

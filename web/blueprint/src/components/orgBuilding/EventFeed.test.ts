import { describe, expect, it } from "vitest";
import {
  applyFilters,
  classify,
  formatEventLine,
} from "./EventFeed";
import type { ObservatoryEvent } from "../../lib/types";

const ev = (over: Partial<ObservatoryEvent>): ObservatoryEvent => ({
  type: "decision.recorded",
  skill: null,
  tool: null,
  domain: null,
  workflow_id: "wf-1",
  ts: 1700000000,
  ...over,
});

describe("EventFeed pure helpers", () => {
  it("classifies decisions/ambient/cadence/meta correctly", () => {
    expect(classify(ev({ type: "decision.recorded" }))).toBe("decisions");
    expect(classify(ev({ type: "ambient.decided" }))).toBe("ambient");
    expect(classify(ev({ type: "cadence.tick" }))).toBe("cadence");
    expect(classify(ev({ type: "workflow.sub_spawned" }))).toBe("meta");
    expect(classify(ev({ type: "workflow.completed" }))).toBeNull();
  });

  it("applyFilters with empty set returns everything", () => {
    const events = [
      ev({ type: "decision.recorded" }),
      ev({ type: "workflow.completed" }),
    ];
    expect(applyFilters(events, new Set())).toHaveLength(2);
  });

  it("applyFilters narrows to selected categories (OR)", () => {
    const events = [
      ev({ type: "decision.recorded" }),
      ev({ type: "ambient.decided" }),
      ev({ type: "workflow.completed" }),
    ];
    const out = applyFilters(events, new Set(["decisions"]));
    expect(out).toHaveLength(1);
    expect(out[0].type).toBe("decision.recorded");
  });

  it("formatEventLine renders timestamp + symbol + type + detail", () => {
    const line = formatEventLine(
      ev({
        type: "decision.recorded",
        decision_id: "DEC-1",
        gate: "finance_signoff",
        persona: "cfo",
      }),
    );
    expect(line).toContain("decision.recorded");
    expect(line).toContain("⚖");
    expect(line).toContain("finance_signoff");
    expect(line).toContain("(cfo)");
  });
});

import { describe, expect, it } from "vitest";
import { humanizeTimeline, type RawTimelineEvent } from "../humanizeTimeline";

const T0 = 1_700_000_000;

function row(over: Partial<RawTimelineEvent>): RawTimelineEvent {
  return { kind: "executor", ts: T0, ...over };
}

describe("humanizeTimeline", () => {
  it("returns an empty array for empty input", () => {
    expect(humanizeTimeline([])).toEqual([]);
  });

  it("filters out tool spans, phase.completed entries, and passing validators", () => {
    const events = humanizeTimeline([
      row({ kind: "tool", label: "tool.fetch_thing" }),
      row({ kind: "executor", label: "phase.completed:Sourcing" }),
      row({ kind: "executor", label: "executor.validate_offer_schema", status: "ok" }),
      // Anchor row so we don't end up with all-empty input.
      row({ kind: "executor", label: "agent_jd_drafter" }),
    ]);
    expect(events).toHaveLength(1);
    expect(events[0].what).toBe("Drafted the job description");
  });

  it("returns an empty array when every row would be filtered out", () => {
    expect(
      humanizeTimeline([
        row({ kind: "tool", label: "tool.x" }),
        row({ kind: "executor", label: "phase.completed:X" }),
      ]),
    ).toEqual([]);
  });

  it("renders a decision row with the persona, verb, and phase", () => {
    const [event] = humanizeTimeline([
      row({
        kind: "decision",
        actor: "cpo",
        label: "budget_check",
        verdict: "approve",
        reason: "Within FY budget.",
      }),
    ]);
    expect(event.who).toBe("Chief Procurement Officer");
    expect(event.what).toBe("Chief Procurement Officer approved Budget Check");
    expect(event.detail).toBe("Within FY budget.");
    expect(event.tone).toBe("ok");
  });

  it("uses tone=bad when the decision is reject and warn for other verdicts", () => {
    const [reject, escalate] = humanizeTimeline([
      row({ kind: "decision", actor: "gc", verdict: "reject", label: "review" }),
      row({ kind: "decision", actor: "gc", verdict: "escalate", label: "review", ts: T0 + 5 }),
    ]);
    expect(reject.tone).toBe("bad");
    expect(reject.what).toContain("rejected");
    expect(escalate.tone).toBe("warn");
    expect(escalate.what).toContain("escalated");
  });

  it("renders phase rows as milestones, both started and completed", () => {
    const [started, completed] = humanizeTimeline([
      row({ kind: "phase", label: "brief_capture", status: "started" }),
      row({ kind: "phase", label: "brief_capture", status: "completed", ts: T0 + 60 }),
    ]);
    expect(started.what).toBe("Started: Brief Capture");
    expect(started.tone).toBe("milestone");
    expect(started.who).toBe("Workflow");
    expect(completed.what).toBe("Brief Capture complete");
    expect(completed.tone).toBe("milestone");
  });

  it("flags a failing schema validator as bad with the validator target", () => {
    const [event] = humanizeTimeline([
      row({
        kind: "executor",
        label: "executor.validate_offer_letter_schema",
        status: "error",
        result_summary: "missing salary field",
      }),
    ]);
    expect(event.what).toBe("Output check failed: offer Letter");
    expect(event.tone).toBe("bad");
    expect(event.who).toBe("AI agent");
    expect(event.detail).toBe("missing salary field");
  });

  it("marks workflow.started as a milestone and suspended as a warn", () => {
    const [started, suspended] = humanizeTimeline([
      row({ label: "workflow.started" }),
      row({ label: "suspended", ts: T0 + 30 }),
    ]);
    expect(started.tone).toBe("milestone");
    expect(started.what).toBe("Workflow started");
    expect(suspended.tone).toBe("warn");
    expect(suspended.what).toBe("Paused — waiting for a person");
  });

  it("marks generic executor failure as bad and success as ok", () => {
    const [okEvent, failedEvent] = humanizeTimeline([
      row({ label: "agent_jd_drafter", status: "ok" }),
      row({ label: "agent_jd_drafter", status: "error", ts: T0 + 1 }),
    ]);
    expect(okEvent.tone).toBe("ok");
    expect(failedEvent.tone).toBe("bad");
  });

  it("computes workflow-relative offsets from the first row's ts", () => {
    const events = humanizeTimeline([
      row({ label: "workflow.started", ts: T0 }),
      row({ label: "agent_jd_drafter", ts: T0 + 64 }),
    ]);
    expect(events[0].offsetSec).toBe(0);
    expect(events[0].when).toBe("+0ms");
    expect(events[1].offsetSec).toBe(64);
    expect(events[1].when).toBe("+1m 4s");
  });

  it("preserves input order even when timestamps are out of order", () => {
    // The contract is order-preserving: humanizeTimeline does not sort. An
    // earlier ts following a later ts collapses to offsetSec=0 (clamped).
    const events = humanizeTimeline([
      row({ label: "workflow.started", ts: T0 + 100 }),
      row({ label: "agent_jd_drafter", ts: T0 + 50 }),
      row({ label: "agent_budget_checker", ts: T0 + 200 }),
    ]);
    expect(events.map((e) => e.what)).toEqual([
      "Workflow started",
      "Drafted the job description",
      "Checked the budget",
    ]);
    expect(events[0].offsetSec).toBe(0);
    expect(events[1].offsetSec).toBe(0); // clamped from a negative diff
    expect(events[2].offsetSec).toBe(100);
  });

  it("falls through to a humanized default for unknown executor labels", () => {
    const [event] = humanizeTimeline([
      row({ label: "agent_some_brand_new_thing" }),
    ]);
    expect(event.what).toBe("Some Brand New Thing ran");
    expect(event.what).not.toMatch(/_/);
    expect(event.who).toBe("AI agent");
  });
});

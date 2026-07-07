import { describe, it, expect } from "vitest";
import { composeReducer, initialState, type ComposeEvent } from "../reducer";

function run(events: ComposeEvent[]) {
  return events.reduce(composeReducer, initialState());
}

describe("composeReducer", () => {
  it("accumulates thoughts and narration", () => {
    const s = run([
      { type: "thought", text: "Reading " },
      { type: "thought", text: "the registry." },
      { type: "narration", text: "On it." },
    ]);
    expect(s.thoughts).toBe("Reading the registry.");
    expect(s.narration).toBe("On it.");
  });

  it("merges tool events by id", () => {
    const s = run([
      { type: "tool", id: "t1", title: "Creating x.py", kind: "edit", status: "pending" },
      { type: "tool", id: "t1", status: "completed", output: "done" },
    ]);
    expect(s.tools).toHaveLength(1);
    expect(s.tools[0]).toMatchObject({ id: "t1", title: "Creating x.py", status: "completed", output: "done" });
  });

  it("tracks stage and plan", () => {
    const s = run([
      { type: "stage", stage: "composing", label: "Composing" },
      { type: "plan", entries: [{ title: "brief", status: "done" }] },
    ]);
    expect(s.stage).toBe("composing");
    expect(s.plan).toEqual([{ title: "brief", status: "done" }]);
  });

  it("sets and clears a question", () => {
    let s = run([{ type: "question", request_id: "r1", text: "CFO?", options: ["CFO"] }]);
    expect(s.question).toMatchObject({ request_id: "r1", text: "CFO?" });
    s = composeReducer(s, { type: "question_cleared", request_id: "r1" });
    expect(s.question).toBeUndefined();
  });

  it("captures done + error", () => {
    const s = run([{ type: "done", workflow_type: "capex", display_name: "Capex" }]);
    expect(s.done).toEqual({ workflow_type: "capex", display_name: "Capex" });
    const e = run([{ type: "error", message: "boom", fatal: true }]);
    expect(e.error).toBe("boom");
  });

  it("retains parsed composition across brief_cleared", () => {
    const parsed = { title: "Capex", workflowType: "capex", function: "finance", steps: [], entities: [], counts: { steps: 0, personae: 0, skills: 0, tools: 0, entities: 0, rules: 0 } };
    let s = run([{ type: "brief", request_id: "b1", yaml: "domain: {}", parsed } as ComposeEvent]);
    expect(s.brief).toMatchObject({ request_id: "b1" });
    expect(s.composition).toEqual(parsed);
    // approving clears the review modal but the canvas keeps the composition
    s = composeReducer(s, { type: "brief_cleared", request_id: "b1" });
    expect(s.brief).toBeUndefined();
    expect(s.composition).toEqual(parsed);
  });

  it("records a decision from an answered question", () => {
    const s = run([
      { type: "question", request_id: "r1", text: "Who signs off?", options: ["CFO"] },
      { type: "decision", question: "Who signs off?", answer: "CFO" },
      { type: "question_cleared", request_id: "r1" },
    ]);
    expect(s.decisions).toEqual([{ question: "Who signs off?", answer: "CFO" }]);
    expect(s.question).toBeUndefined();
  });
});

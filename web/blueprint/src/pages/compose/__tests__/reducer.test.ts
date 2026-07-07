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
});

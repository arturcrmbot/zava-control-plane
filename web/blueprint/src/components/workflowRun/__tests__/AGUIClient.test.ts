import { describe, expect, it, vi } from "vitest";
import { connectWorkflowRun } from "../AGUIClient";

describe("connectWorkflowRun", () => {
  it("returns a subscription that calls onEvent for each AG-UI event", async () => {
    const events: any[] = [];
    const fakeAgent = {
      runAgent: vi.fn(async ({ onEvent }: any) => {
        onEvent({ type: "RUN_STARTED", runId: "r1", threadId: "r1" });
        onEvent({ type: "TEXT_MESSAGE_START", messageId: "m1",
                  role: "assistant" });
        onEvent({ type: "RUN_FINISHED", runId: "r1", threadId: "r1" });
      }),
    };
    const sub = connectWorkflowRun("r1", (e) => events.push(e), {
      agentFactory: () => fakeAgent as any,
    });
    await sub.done;
    expect(events.map((e) => e.type)).toEqual([
      "RUN_STARTED", "TEXT_MESSAGE_START", "RUN_FINISHED",
    ]);
  });
});

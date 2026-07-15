import { describe, it, expect } from "vitest";
import { initialRunState, applyEvent } from "../runReducer";

describe("runReducer", () => {
  it("appends a message on TEXT_MESSAGE_CONTENT", () => {
    let s = initialRunState();
    s = applyEvent(s, { type: "TEXT_MESSAGE_START",
                        messageId: "m1", role: "assistant" } as any);
    s = applyEvent(s, { type: "TEXT_MESSAGE_CONTENT",
                        messageId: "m1", delta: "Hello " } as any);
    s = applyEvent(s, { type: "TEXT_MESSAGE_CONTENT",
                        messageId: "m1", delta: "world" } as any);
    s = applyEvent(s, { type: "TEXT_MESSAGE_END", messageId: "m1" } as any);
    expect(s.messages).toEqual([
      { id: "m1", role: "assistant", text: "Hello world", closed: true },
    ]);
  });

  it("replays a message idempotently when the stream reconnects", () => {
    let s = initialRunState();
    const events = [
      { type: "TEXT_MESSAGE_START", messageId: "m1", role: "assistant" },
      { type: "TEXT_MESSAGE_CONTENT", messageId: "m1", delta: "Hello" },
      { type: "TEXT_MESSAGE_END", messageId: "m1" },
    ];

    for (const event of [...events, ...events]) {
      s = applyEvent(s, event as any);
    }

    expect(s.messages).toEqual([
      { id: "m1", role: "assistant", text: "Hello", closed: true },
    ]);
  });

  it("records tool calls with args + status", () => {
    let s = initialRunState();
    s = applyEvent(s, { type: "TOOL_CALL_START", toolCallId: "tc1",
                        toolCallName: "policy_search" } as any);
    s = applyEvent(s, { type: "TOOL_CALL_ARGS", toolCallId: "tc1",
                        delta: '{"q":"x"}' } as any);
    s = applyEvent(s, { type: "TOOL_CALL_END", toolCallId: "tc1" } as any);
    expect(s.toolCalls).toEqual([
      { id: "tc1", name: "policy_search", args: '{"q":"x"}', closed: true },
    ]);
  });

  it("replays a tool call idempotently when the stream reconnects", () => {
    let s = initialRunState();
    const events = [
      { type: "TOOL_CALL_START", toolCallId: "tc1", toolCallName: "policy_search" },
      { type: "TOOL_CALL_ARGS", toolCallId: "tc1", delta: '{"q":"x"}' },
      { type: "TOOL_CALL_END", toolCallId: "tc1" },
    ];

    for (const event of [...events, ...events]) {
      s = applyEvent(s, event as any);
    }

    expect(s.toolCalls).toEqual([
      { id: "tc1", name: "policy_search", args: '{"q":"x"}', closed: true },
    ]);
  });

  it("applies STATE_DELTA as JSON patch", () => {
    let s = initialRunState();
    s = applyEvent(s, {
      type: "STATE_DELTA",
      delta: [{ op: "add", path: "/entities/person/p1",
                value: { name: "Ada" } }],
    } as any);
    expect(s.state).toEqual({
      entities: { person: { p1: { name: "Ada" } } },
    });
  });

  it("tracks RUN_INTERRUPTED with prompt + persona", () => {
    let s = initialRunState();
    s = applyEvent(s, { type: "RUN_INTERRUPTED",
                        reason: "awaiting_approval",
                        persona: "hiring_manager" } as any);
    expect(s.interrupt).toEqual({
      reason: "awaiting_approval", persona: "hiring_manager",
    });
  });

  it("tracks RUN_FINISHED", () => {
    let s = initialRunState();
    s = applyEvent(s, { type: "RUN_FINISHED", runId: "r1",
                        threadId: "r1" } as any);
    expect(s.finished).toBe(true);
  });
});

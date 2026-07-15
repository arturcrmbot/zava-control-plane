// @vitest-environment jsdom
import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DrawerReasoning from "../DrawerReasoning";

class FakeEventSource {
  static CLOSED = 2;
  static instance: FakeEventSource;

  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  readyState = 1;

  constructor(_url: string) {
    FakeEventSource.instance = this;
  }

  close() {}
}

describe("DrawerReasoning replay", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders one message when a reconnect replays the same message id", () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <DrawerReasoning
        data={{ workflow: { id: "workflow-replay-idempotency" } } as any}
      />,
    );
    const events = [
      { type: "TEXT_MESSAGE_START", messageId: "m1", role: "assistant" },
      { type: "TEXT_MESSAGE_CONTENT", messageId: "m1", delta: "Hello" },
      { type: "TEXT_MESSAGE_END", messageId: "m1" },
      {
        type: "TOOL_CALL_START",
        toolCallId: "tc1",
        toolCallName: "policy_search",
      },
      { type: "TOOL_CALL_ARGS", toolCallId: "tc1", delta: '{"q":"x"}' },
      { type: "TOOL_CALL_END", toolCallId: "tc1" },
    ];

    act(() => {
      for (const event of [...events, ...events]) {
        FakeEventSource.instance.onmessage?.({ data: JSON.stringify(event) });
      }
    });

    expect(screen.getAllByText("Hello")).toHaveLength(1);
    expect(screen.getAllByText("policy_search")).toHaveLength(1);
    expect(consoleError).not.toHaveBeenCalled();
  });
});

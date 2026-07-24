// @vitest-environment jsdom
import { act, cleanup, render, screen } from "@testing-library/react";
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
    cleanup();
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

  it.each([
    [{ type: "CUSTOM", name: "hitl.resumed", value: {} }],
    [{ type: "RUN_STARTED", runId: "run-resumed" }],
    [{ type: "RUN_FINISHED", runId: "run-finished" }],
    [{ type: "RUN_ERROR", message: "terminal failure" }],
  ])("clears a replayed interrupt when the run resumes or terminates", (nextEvent) => {
    vi.stubGlobal("EventSource", FakeEventSource);
    render(
      <DrawerReasoning
        data={{ workflow: { id: `workflow-clear-${nextEvent.type}` } } as any}
      />,
    );

    act(() => {
      FakeEventSource.instance.onmessage?.({
        data: JSON.stringify({
          type: "RUN_INTERRUPTED",
          reason: "approval required",
          persona: "network-director",
        }),
      });
      FakeEventSource.instance.onmessage?.({ data: JSON.stringify(nextEvent) });
    });

    const section = screen.getByRole("heading", { name: /Live reasoning/i }).closest("section");
    expect(section?.textContent).not.toContain("network-director");
  });

  it("describes a finished deterministic run without implying it is listening", () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    render(
      <DrawerReasoning
        data={{ workflow: { id: "workflow-finished-deterministic" } } as any}
      />,
    );

    act(() => {
      FakeEventSource.instance.onopen?.();
      FakeEventSource.instance.onmessage?.({
        data: JSON.stringify({ type: "RUN_FINISHED", runId: "run-finished" }),
      });
    });

    expect(screen.getByText(/Deterministic execution — no agent session was used/i)).toBeTruthy();
    expect(screen.queryByText(/Listening for agent events/i)).toBeNull();
  });

  it("uses completed workflow state when a replay has no lifecycle events", () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    render(
      <DrawerReasoning
        data={{
          workflow: { id: "workflow-completed-without-events", status: "completed" },
        } as any}
      />,
    );

    act(() => {
      FakeEventSource.instance.onopen?.();
    });

    expect(screen.getByText(/Deterministic execution — no agent session was used/i)).toBeTruthy();
    expect(screen.queryByText(/Listening for agent events/i)).toBeNull();
  });

  it.each(["reasoning", "agent", "agentOutput"])(
    "does not claim deterministic execution when replay timeline has %s evidence",
    (kind) => {
      vi.stubGlobal("EventSource", FakeEventSource);
      render(
        <DrawerReasoning
          data={{
            workflow: {
              id: `workflow-restored-${kind}`,
              status: "completed",
            },
            timeline: [{
              id: `${kind}:persisted`,
              ts: 1_234.5,
              kind,
              label: "risk-reviewer",
              status: "completed",
              messages: [{ role: "assistant", content: "Checked evidence" }],
            }],
          } as any}
        />,
      );

      expect(
        screen.queryByText(/Deterministic execution — no agent session was used/i),
      ).toBeNull();
      expect(
        screen.getByText(/Agent evidence is available in the Activity timeline/i),
      ).toBeTruthy();
    },
  );
});

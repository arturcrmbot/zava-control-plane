// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RunPanel } from "../RunPanel";
import { initialRunState, applyEvent } from "../runReducer";

describe("RunPanel", () => {
  it("renders messages, tool calls and state", () => {
    let s = initialRunState();
    s = applyEvent(s, { type: "TEXT_MESSAGE_START", messageId: "m1",
                        role: "assistant" } as any);
    s = applyEvent(s, { type: "TEXT_MESSAGE_CONTENT", messageId: "m1",
                        delta: "Hello" } as any);
    s = applyEvent(s, { type: "TEXT_MESSAGE_END", messageId: "m1" } as any);
    s = applyEvent(s, { type: "TOOL_CALL_START", toolCallId: "tc1",
                        toolCallName: "policy_search" } as any);

    render(<RunPanel runId="hiring-1" state={s} />);
    expect(screen.getByText("Hello")).toBeTruthy();
    expect(screen.getByText("policy_search")).toBeTruthy();
    expect(screen.getByText(/hiring-1/)).toBeTruthy();
  });

  it("renders an interrupt banner when present", () => {
    let s = initialRunState();
    s = applyEvent(s, { type: "RUN_INTERRUPTED",
                        reason: "awaiting_approval",
                        persona: "hiring_manager" } as any);
    render(<RunPanel runId="r" state={s} />);
    expect(screen.getByText(/awaiting_approval/)).toBeTruthy();
    expect(screen.getByText(/hiring_manager/)).toBeTruthy();
  });
});

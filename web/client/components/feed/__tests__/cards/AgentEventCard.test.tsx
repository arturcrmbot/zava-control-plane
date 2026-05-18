// @vitest-environment jsdom
// web/client/components/feed/__tests__/cards/AgentEventCard.test.tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import AgentEventCard from "@client/components/feed/cards/AgentEventCard";
import type { AgentEventItem } from "@shared/feedItems";

afterEach(cleanup);

const item: AgentEventItem = {
  type: "agent-event", id: "agent-event:fm:1:0", timestamp: 100,
  severity: null, source: "fleet-manager", kind: "wakeup",
  data: { workflow_id: "WF-1", reason: "SLA breach in 8m" },
  workflowId: "WF-1",
};

describe("AgentEventCard", () => {
  it("renders the kind and source", () => {
    render(<MemoryRouter><AgentEventCard item={item} /></MemoryRouter>);
    expect(screen.getByText(/wakeup/i)).toBeTruthy();
    expect(screen.getByText(/Fleet Manager/i)).toBeTruthy();
  });
  it("Expand JSON toggles a <pre> inline (not a drawer)", () => {
    render(<MemoryRouter><AgentEventCard item={item} /></MemoryRouter>);
    expect(screen.queryByText(/SLA breach in 8m/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Expand JSON/i }));
    expect(screen.getByText(/SLA breach in 8m/)).toBeTruthy();
  });
});

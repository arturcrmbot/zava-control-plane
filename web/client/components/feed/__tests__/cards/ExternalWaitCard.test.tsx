// @vitest-environment jsdom
// web/client/components/feed/__tests__/cards/ExternalWaitCard.test.tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import ExternalWaitCard from "@client/components/feed/cards/ExternalWaitCard";
import { ResolutionProvider } from "@client/hooks/useResolutionStore";
import type { ExternalWaitItem } from "@shared/feedItems";

afterEach(cleanup);

const item: ExternalWaitItem = {
  type: "external-wait", id: "external-wait:WF-7", timestamp: 100,
  workflowId: "WF-7", domain: "hiring", severity: "medium",
  awaitingReason: "candidate-reply",
  workflow: {
    id: "WF-7", type: "hiring", status: "in_progress",
    currentPhase: "Sourcing", createdAt: 100, slaDueAt: 9999,
    jurisdiction: "UK", agency: "Z", actionLedger: [],
    tokensSpent: 0, costUSD: 0,
    metadata: { wait_kind: "external_party", awaiting_reason: "candidate-reply" },
  },
};

describe("ExternalWaitCard", () => {
  it("renders the awaiting reason", () => {
    render(
      <MemoryRouter>
        <ResolutionProvider><ExternalWaitCard item={item} /></ResolutionProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText(/candidate-reply/i)).toBeTruthy();
  });
  it("offers Nudge / Reassign / View token buttons", () => {
    render(
      <MemoryRouter>
        <ResolutionProvider><ExternalWaitCard item={item} /></ResolutionProvider>
      </MemoryRouter>,
    );
    expect(screen.getByRole("button", { name: /Nudge/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Reassign/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /View token/i })).toBeTruthy();
  });
});

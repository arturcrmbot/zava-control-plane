// @vitest-environment jsdom
//
// AC #8 — SSC Reviewer queue. Filters /api/exceptions to unresolved items
// and sorts by severity then created_at.
import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import ReviewerQueue from "@client/routes/ReviewerQueue";

beforeEach(() => {
  // Stub EventSource so the useSSE hook inside useExceptions doesn't open a real connection.
  (globalThis as any).EventSource = class {
    onmessage: ((ev: MessageEvent) => void) | null = null;
    addEventListener() {}
    close() {}
  };
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ReviewerQueue", () => {
  it("renders empty state when there are no exceptions", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    } as Response);

    render(
      <MemoryRouter>
        <ReviewerQueue />
      </MemoryRouter>,
    );
    expect(screen.getByText(/SSC Reviewer Queue/i)).toBeTruthy();
    await waitFor(() => {
      expect(screen.getByText(/No items awaiting reviewer decision/i)).toBeTruthy();
    });
  });

  it("filters resolved exceptions out and sorts critical first", async () => {
    const exceptions = [
      {
        id: "EXC-1",
        workflowId: "EXP-100",
        composedBy: "fleet-manager",
        severity: "medium",
        category: "threshold-exceeded",
        summary: "Medium severity item",
        recommendation: "review-now",
        options: [],
        relatedPolicyRefs: [],
        confidence: 0.8,
        createdAt: 100,
      },
      {
        id: "EXC-2",
        workflowId: "EXP-200",
        composedBy: "fleet-manager",
        severity: "critical",
        category: "compliance",
        summary: "Critical severity item",
        recommendation: "escalate",
        options: [],
        relatedPolicyRefs: [],
        confidence: 0.9,
        createdAt: 200,
      },
      {
        id: "EXC-3",
        workflowId: "EXP-300",
        composedBy: "fleet-manager",
        severity: "high",
        category: "duplicate-invoice",
        summary: "Already resolved",
        recommendation: "x",
        options: [],
        relatedPolicyRefs: [],
        confidence: 0.7,
        createdAt: 50,
        resolvedAt: 60,
      },
    ];
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => exceptions,
    } as Response);

    render(
      <MemoryRouter>
        <ReviewerQueue />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("EXP-200")).toBeTruthy();
      expect(screen.getByText("EXP-100")).toBeTruthy();
      expect(screen.queryByText("EXP-300")).toBeNull();
    });

    expect(screen.getByText(/2 items awaiting/i)).toBeTruthy();
  });

  it("shows the recommendation label and option summary", async () => {
    const exceptions = [
      {
        id: "EXC-A",
        workflowId: "EXP-A",
        composedBy: "fleet-manager",
        severity: "high",
        category: "compliance",
        summary: "Receipt mismatch",
        recommendation: "request-justification",
        options: [
          { label: "Accept", action: "accept", nonRevocable: false, recommended: true },
          { label: "Escalate", action: "escalate", nonRevocable: false, recommended: false },
        ],
        relatedPolicyRefs: [],
        confidence: 0.85,
        createdAt: 100,
      },
    ];
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => exceptions,
    } as Response);

    render(
      <MemoryRouter>
        <ReviewerQueue />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText(/request-justification/)).toBeTruthy();
    });
    expect(screen.getByText(/Accept \/ Escalate/)).toBeTruthy();
  });
});

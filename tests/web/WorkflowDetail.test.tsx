// @vitest-environment jsdom
//
// POC2 §4.21 AG-UI render — WorkflowDetail must render the agent-emitted
// candidate scorecard when the cv_crystalliser agent has populated
// `workflow.agentOutputs.cv_crystalliser.componentSpec`. Section is gated
// to hiring workflows with a non-empty spec; expense_claim and empty-spec
// hiring workflows must NOT render the section.
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import WorkflowDetail from "@client/routes/WorkflowDetail";

type DetailPayload = Record<string, unknown>;

function mountAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/workflows/:id" element={<WorkflowDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

const baseWorkflow = {
  id: "HIRE-1",
  type: "hiring",
  status: "in_progress",
  currentPhase: "Triage",
  createdAt: 0,
  slaDueAt: 0,
  jurisdiction: "London-WPP",
  agency: "WPP-HR",
  actionLedger: [],
  tokensSpent: 0,
  costUSD: 0,
  metadata: {},
};

const baseEconomics = {
  computeCostUsd: 0, modelCalls: 0, toolCalls: 0,
  daysElapsed: 0, slaToken: "ok",
};

function makeDetail(workflow: Record<string, unknown>): DetailPayload {
  return {
    workflow,
    phases: [],
    spans: [],
    amplifications: [],
    activeException: null,
    mcpCalls: [],
    economics: baseEconomics,
    narrative: null,
  };
}

describe("WorkflowDetail — POC2 §4.21 candidate scorecard", () => {
  beforeEach(() => {
    (globalThis as any).EventSource = class {
      addEventListener() {}
      close() {}
    };
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("renders the candidate scorecard for a hiring workflow with a populated componentSpec", async () => {
    const detail = makeDetail({
      ...baseWorkflow,
      id: "HIRE-1",
      agentOutputs: {
        cv_crystalliser: {
          profile: { current_title: "Senior Data Engineer" },
          componentSpec: [
            { kind: "fact_grid", title: "Profile", facts: [{ label: "Role", value: "SDE" }] },
            { kind: "skill_chips", title: "Top skills", skills: ["python", "spark"] },
          ],
        },
      },
    });
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true, json: async () => detail,
    } as Response);

    mountAt("/workflows/HIRE-1");

    expect(await screen.findByTestId("candidate-scorecard")).toBeTruthy();
    // Both spec entries' titles render through AgentDrivenComponent.
    await waitFor(() => expect(screen.getAllByText("Profile").length).toBeGreaterThan(0));
    expect(screen.getByText("Top skills")).toBeTruthy();
  });

  it("does not render the scorecard section for expense_claim workflows", async () => {
    const detail = makeDetail({
      ...baseWorkflow,
      id: "EXP-1",
      type: "expense-claim",
      currentPhase: "Classify",
      claim: {
        claimId: "CLM-1", employeeId: "EMP-1", submittedAt: "2026-04-01T10:00:00",
        market: "UK", currency: "GBP", category: "meals", vendor: "Côte",
        amount: 89.5, attendees: 3, emsSource: "concur",
      },
      // Even with a stray componentSpec on a non-hiring workflow, we must
      // not render the section — gating is on type === "hiring".
      agentOutputs: {
        cv_crystalliser: {
          componentSpec: [{ kind: "fact_grid", title: "Profile", facts: [] }],
        },
      },
    });
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true, json: async () => detail,
    } as Response);

    mountAt("/workflows/EXP-1");

    // Wait for the workflow header to land so we know the page rendered.
    // EMP-1 appears in multiple text nodes (header subtitle + receipt panel)
    // so use getAllByText to avoid testing-library's multi-match throw.
    await waitFor(() => expect(screen.getAllByText(/EMP-1/).length).toBeGreaterThan(0));
    expect(screen.queryByTestId("candidate-scorecard")).toBeNull();
  });

  it("does not render the scorecard when componentSpec is empty", async () => {
    const detail = makeDetail({
      ...baseWorkflow,
      id: "HIRE-2",
      agentOutputs: {
        cv_crystalliser: { profile: {}, componentSpec: [] },
      },
    });
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true, json: async () => detail,
    } as Response);

    mountAt("/workflows/HIRE-2");

    // Wait for the workflow id title to land so we know render finished.
    await waitFor(() => expect(screen.getAllByText(/HIRE-2/).length).toBeGreaterThan(0));
    expect(screen.queryByTestId("candidate-scorecard")).toBeNull();
  });
});

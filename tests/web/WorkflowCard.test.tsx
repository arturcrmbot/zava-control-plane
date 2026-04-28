// @vitest-environment jsdom
//
// AC #9 ("system-agnostic Control Plane"): the FleetDashboard must not
// reveal `ems_source` on the card. Per spec §7 #9 the source EMS is only
// shown in the audit drawer / WorkflowDetail subtitle.
import { describe, expect, it, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import WorkflowCard from "@client/components/WorkflowCard";
import type { Workflow } from "@shared/types";

afterEach(() => cleanup());

function makeWorkflow(overrides: Partial<Workflow> = {}): Workflow {
  return {
    id: "EXP-0042",
    type: "expense-claim",
    status: "in_progress",
    currentPhase: "Classify",
    createdAt: 0,
    slaDueAt: 0,
    jurisdiction: "UK-WPP",
    agency: "Mindshare",
    actionLedger: [],
    tokensSpent: 0,
    costUSD: 0,
    claim: {
      claimId: "CLM-0042",
      employeeId: "EMP-0001",
      submittedAt: "2026-04-01T10:00:00",
      market: "UK",
      currency: "GBP",
      category: "meals",
      vendor: "Côte Brasserie",
      amount: 89.5,
      attendees: 3,
      emsSource: "concur",
    },
    verdict: "amber",
    ...overrides,
  };
}

describe("WorkflowCard — AC #9 system-agnostic Control Plane", () => {
  it("does not render the EMS source on a Concur claim", () => {
    render(
      <MemoryRouter>
        <WorkflowCard w={makeWorkflow({ claim: { ...makeWorkflow().claim!, emsSource: "concur" } })} />
      </MemoryRouter>,
    );
    // The card must not leak the EMS source name.
    expect(screen.queryByText(/concur/i)).toBeNull();
    expect(screen.queryByText(/workday/i)).toBeNull();
  });

  it("does not render the EMS source on a Workday claim", () => {
    render(
      <MemoryRouter>
        <WorkflowCard w={makeWorkflow({ claim: { ...makeWorkflow().claim!, emsSource: "workday" } })} />
      </MemoryRouter>,
    );
    expect(screen.queryByText(/concur/i)).toBeNull();
    expect(screen.queryByText(/workday/i)).toBeNull();
  });

  it("renders claim subtitle (employee id) + amount + verdict but not ems_source", () => {
    render(
      <MemoryRouter>
        <WorkflowCard w={makeWorkflow()} />
      </MemoryRouter>,
    );
    // Visible: employee id, currency+amount, verdict, phase.
    expect(screen.getByText("EMP-0001")).toBeTruthy();
    expect(screen.getByText(/GBP/)).toBeTruthy();
    expect(screen.getByText("amber")).toBeTruthy();
    expect(screen.getByText("Classify")).toBeTruthy();
  });
});

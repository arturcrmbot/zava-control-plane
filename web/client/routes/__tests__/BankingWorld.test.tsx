// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ComponentProps } from "react";
import type { WorldEvent, WorldState } from "@client/hooks/useWorldSimulation";
import BankingWorld from "../BankingWorld";

// Event types and payload shapes are the ones the banking world journal
// actually carries for a hero run (see the recorded tape).
function ev(seq: number, type: string, trace_id: string, payload: Record<string, unknown> = {}, actor_id: string | null = null, target_id: string | null = null): WorldEvent {
  return { seq, event_id: `evt-${seq}`, sim_time: seq, type, actor_id, target_id, cause_event_id: null, trace_id, payload };
}

const REFUSAL =
  "fraud_decision_manager is not authorised to approve GBP 85,000.00 for synthetic-app-fraud-reimbursement: " +
  "value exceeds delegated authority (matched rule AUTH-financial_crime_lead-banking.commit_reimbursement_decision)";

const APPROVED_TRACE: WorldEvent[] = [
  ev(10, "banking.app_fraud.claim_raised", "evt-10", { claim_id: "SYN-CLAIM-0031", customer_id: "SYN-CUST-0007", amount_gbp: 18_400, vulnerability_flag: false, function: "retail-banking" }, "SYN-CLAIM-0031", "SYN-BENE-002"),
  ev(11, "sensor.tripped", "evt-10", { sensor_id: "sensor:app_fraud_claim", claim_id: "SYN-CLAIM-0031", function: "retail-banking" }, "sensor:app_fraud_claim", "SYN-CLAIM-0031"),
  ev(12, "objective.opened", "evt-10", { owner_function: "retail-banking", status: "open" }, "retail-banking", "SYN-CLAIM-0031"),
  ev(13, "responder.requested", "evt-10", { workflow_id: "bapp-evt-11", workflow_type: "app-fraud-reimbursement" }),
];
const APPROVED_OUTCOME: WorldEvent[] = [
  ev(14, "responder.decided", "evt-10", { workflow_id: "bapp-evt-11", command: { payload: { option_id: "SYN-APP-OPTION-REIMBURSE-FULL", value_gbp: 18_400 } } }),
  ev(15, "banking.investigation.opened", "evt-10", { claim_id: "SYN-CLAIM-0031", beneficiary_id: "SYN-BENE-002", holder_id: "SYN-CORP-014", holder_kind: "corporate" }, "SYN-INV-SYN-CLAIM-0031", "SYN-BENE-002"),
  ev(16, "banking.reimbursement.applied", "evt-10", { claim_id: "SYN-CLAIM-0031", value_gbp: 18_400 }, "SYN-CLAIM-0031", "SYN-BENE-002"),
  ev(17, "evaluation.resolved", "evt-10", {}, "retail-banking", "retail-banking"),
  ev(18, "objective.resolved", "evt-10", { status: "resolved" }, "retail-banking", "SYN-CLAIM-0031"),
];
const REFUSED_TRACE: WorldEvent[] = [
  ev(20, "banking.app_fraud.claim_raised", "evt-20", { claim_id: "SYN-CLAIM-0033", customer_id: "SYN-CUST-0011", amount_gbp: 92_000, vulnerability_flag: false, function: "retail-banking" }, "SYN-CLAIM-0033", "SYN-BENE-003"),
  ev(21, "sensor.tripped", "evt-20", { sensor_id: "sensor:app_fraud_claim", claim_id: "SYN-CLAIM-0033", function: "retail-banking" }, "sensor:app_fraud_claim", "SYN-CLAIM-0033"),
  ev(22, "objective.opened", "evt-20", { owner_function: "retail-banking", status: "open" }, "retail-banking", "SYN-CLAIM-0033"),
  ev(23, "responder.requested", "evt-20", { workflow_id: "bapp-evt-21", workflow_type: "app-fraud-reimbursement" }),
  ev(24, "responder.deferred", "evt-20", { workflow_id: "bapp-evt-21", reasoning: REFUSAL }),
  ev(25, "objective.failed", "evt-20", { status: "failed" }, "retail-banking", "SYN-CLAIM-0033"),
];
const ROUTINE = ev(1, "banking.payment.settled", "evt-1", { rail_id: "SYN-RAIL-FPS", amount_gbp: 1840, function: "payments" }, "SYN-PAY-0100", "SYN-RAIL-FPS");

function claim(id: string, extra: Record<string, unknown>) {
  return { id, customer_id: "SYN-CUST", payment_id: "SYN-PAY", beneficiary_id: "SYN-BENE", rail_id: "SYN-RAIL-FPS", amount_gbp: 1000, vulnerability_flag: false, status: "reported", recoverable_gbp: 500, raised: false, ...extra };
}

const STATE = {
  enabled: true,
  scenario: "banking",
  status: "running",
  sim_time: 1053,
  seed: 42,
  objectives: [],
  bank: {
    customer_count: 2400,
    vulnerable_customer_count: 84,
    payments_settled_total: 777,
    settled_value_gbp: 253_000_000,
    positions_marked_total: 100,
    positions_mtm_gbp: 253_000_000,
  },
  payment_rails: [
    { id: "SYN-RAIL-FPS", display_name: "Faster Payments", settlement_window_minutes: 2, in_flight_count: 240, status: "operational" },
    { id: "SYN-RAIL-BACS", display_name: "Bulk Clearing", settlement_window_minutes: 4320, in_flight_count: 691, status: "operational" },
  ],
  recent_settlements: [{ payment_id: "SYN-PAY-0100", rail_id: "SYN-RAIL-FPS", amount_gbp: 1840, sim_time: 418, event_id: "evt-settle" }],
  fraud_claims: [
    claim("SYN-CLAIM-0031", { amount_gbp: 18_400, status: "reimbursed", raised: true }),
    claim("SYN-CLAIM-0032", { amount_gbp: 6750, vulnerability_flag: true }),
    claim("SYN-CLAIM-0033", { amount_gbp: 92_000, rail_id: "SYN-RAIL-CHAPS", raised: true }),
  ],
  reimbursement_evaluations: [{ id: "eval-1", claim_id: "SYN-CLAIM-0031", status: "completed", reimbursed_gbp: 18_400 }],
  beneficiaries: [],
  investigations: [],
  counterparties: [],
  credit_limits: [],
  exposures: [],
  positions: [],
} satisfies WorldState;

const EVENTS = [ROUTINE, ...APPROVED_TRACE, ...APPROVED_OUTCOME, ...REFUSED_TRACE];

let queue: unknown[] = [];
let details: Record<string, unknown> = {};
let workflows: unknown[] = [];

function renderBank(overrides: Partial<ComponentProps<typeof BankingWorld>> = {}) {
  const props = {
    state: STATE,
    events: EVENTS,
    loading: false,
    error: null,
    onRunScenario: vi.fn(async () => {}),
    onRunProcess: vi.fn(async () => {}),
    ...overrides,
  };
  return { ...render(<BankingWorld {...props} />), props };
}

beforeEach(() => {
  queue = [];
  details = {};
  workflows = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const path = String(url);
    const body = path === "/api/workflows" ? workflows
      : path.startsWith("/api/workflows/") ? details[path] ?? {}
      : path.startsWith("/api/simulator/inject-burst") ? { ok: true }
      : queue;
    return new Response(JSON.stringify(body), { status: 200 });
  }));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("BankingWorld", () => {
  it("renders live bank counters in the bank's language", () => {
    renderBank();
    expect(screen.getByTestId("bank-stat-payments").textContent).toContain("777");
    expect(screen.getByTestId("bank-stat-payments").textContent).toContain("£253m");
    expect(screen.getByTestId("bank-stat-customers").textContent).toContain("2,400");
    expect(screen.getByText("3-day cycle")).toBeTruthy();
    expect(screen.getByText("2 min window")).toBeTruthy();
  });

  it("raises a new claim of each kind from the world", () => {
    for (const [label, id] of [
      ["Fraud claim reported", "new-fraud-claim"],
      ["High-value claim", "new-fraud-claim:high-value"],
      ["Vulnerable customer claim", "new-fraud-claim:vulnerable"],
    ] as const) {
      cleanup();
      const onRunScenario = vi.fn(async () => {});
      renderBank({ onRunScenario });
      fireEvent.click(screen.getByRole("button", { name: label }));
      expect(onRunScenario).toHaveBeenCalledWith(id);
    }
  });

  it("opens a new autonomous case of the chosen process", () => {
    renderBank();
    fireEvent.click(screen.getByRole("button", { name: "Mule activity detected" }));
    expect(fetch).toHaveBeenCalledWith(
      "/api/simulator/inject-burst?n=1&workflow_type=mule-account-investigation",
      { method: "POST" },
    );
  });

  it("lists recent cases newest first, each one openable", async () => {
    workflows = [
      { id: "BMUL-0001", type: "mule-account-investigation", status: "completed", currentPhase: "Verify Disposition", createdAt: 10, metadata: {} },
      { id: "bapp-evt-00000200", type: "app-fraud-reimbursement", status: "failed", currentPhase: "Decide Reimbursement", createdAt: 20, metadata: { rejected: true } },
      { id: "VKY-0001", type: "vendor-kyc", status: "in_progress", createdAt: 30, metadata: {} },
    ];
    renderBank();
    const refused = await screen.findByTestId("case-bapp-evt-00000200");
    expect(refused.getAttribute("href")).toBe("/workflows/bapp-evt-00000200");
    expect(refused.textContent).toContain("refused by authority");
    expect(screen.getByTestId("case-BMUL-0001").textContent).toContain("decided");
    // Another pack's workflow never appears on the bank's floor.
    expect(screen.queryByTestId("case-VKY-0001")).toBeNull();
    const rows = screen.getByTestId("recent-cases").querySelectorAll("a");
    expect(rows[0].getAttribute("data-testid")).toBe("case-bapp-evt-00000200");
  });

  it("never shows a dormant claim as open work", () => {
    renderBank();
    expect(screen.queryByTestId("claim-SYN-CLAIM-0032")).toBeNull();
    expect(screen.getByTestId("bank-stat-claims").textContent).toContain("2 raised");
  });

  it("invites the presenter to start a story when nothing is raised", () => {
    renderBank({ state: { ...STATE, fraud_claims: STATE.fraud_claims.map((c) => ({ ...c, raised: false })) }, events: [ROUTINE] });
    expect(screen.getByTestId("claims-empty")).toBeTruthy();
    expect(screen.queryByTestId("banking-intervention")).toBeNull();
  });

  it("says who is authorised when governance refuses", () => {
    renderBank();
    const outcome = screen.getByTestId("claim-outcome-SYN-CLAIM-0033");
    expect(outcome.textContent).toBe("Refused by authority · needs Financial crime lead");
    const chain = screen.getByTestId("banking-intervention").textContent ?? "";
    expect(chain).toContain("Refused by authority");
    expect(chain).toContain("needs Financial crime lead");
    expect(chain).toContain("Escalation required");
  });

  it("shows an approved claim's reimbursement", () => {
    renderBank();
    expect(screen.getByTestId("claim-outcome-SYN-CLAIM-0031").textContent).toBe("Reimbursed in full · £18,400");
  });

  it("counts humans in the loop from the real operator queue", async () => {
    queue = [{ id: "exc-1", workflowId: "bapp-evt-11", summary: "Workflow suspended for approval: awaiting_approval", recommendation: "Awaiting Fleet Manager reasoning." }];
    details["/api/workflows/bapp-evt-11"] = {
      workflow: {
        payload: {
          hitl_context: {
            persona: "fraud_decision_manager",
            phase: "Decide Reimbursement",
            selected_option: { option_id: "SYN-APP-OPTION-REIMBURSE-FULL", impact: "Reimburse the customer in full", value_gbp: 18_400 },
            ranking: { reasoning: "The only admitted option reimburses the customer in full. It maximises recovery. A third sentence." },
            authority: { allowed: true },
          },
        },
      },
    };
    renderBank({
      state: { ...STATE, fraud_claims: [claim("SYN-CLAIM-0031", { amount_gbp: 18_400, raised: true })], reimbursement_evaluations: [] },
      events: [ROUTINE, ...APPROVED_TRACE],
    });
    const band = await screen.findByTestId("pending-decisions");
    expect(screen.getByTestId("decisions-waiting").textContent).toBe("1");
    expect(within(band).getByRole("link", { name: "Review & decide →" }).getAttribute("href")).toBe("/workflows/bapp-evt-11");
    expect(screen.getByTestId("claim-outcome-SYN-CLAIM-0031").textContent).toBe("Waiting for the fraud decision manager");
    // The card says who decides and what the agents recommend, not the queue's placeholder.
    expect(await within(band).findByText("Fraud decision manager · Decide Reimbursement")).toBeTruthy();
    const card = within(band).getByTestId("pending-bapp-evt-11").textContent ?? "";
    expect(card).toContain("Agents recommend: Reimburse the customer in full · £18,400");
    expect(card).toContain("It maximises recovery.");
    expect(card).not.toContain("A third sentence");
    expect(card).toContain("Within delegated authority");
    expect(card).not.toContain("Fleet Manager");
  });

  it("tells the story of each persona's judgement before the outcome", async () => {
    details["/api/workflows/bapp-evt-11"] = { workflow: { payload: { decisions: [
      { persona_role: "fraud_decision_manager", verdict: "hold", decided_by: "laya",
        judgement: { summary: "Held for a closer look: the agent's reasoning says there is no vulnerability marker, but the record shows one. Handed to the Financial crime lead." } },
      { persona_role: "financial_crime_lead", verdict: "approve", decided_by: "llm",
        judgement: { summary: "Deep review: The record is consistent." } },
    ] } } };
    renderBank({ events: [ROUTINE, ...APPROVED_TRACE, ...APPROVED_OUTCOME] });
    const strip = screen.getByTestId("banking-intervention");
    expect(await within(strip).findByText("Fraud decision manager held it")).toBeTruthy();
    const chain = strip.textContent ?? "";
    expect(chain).toContain("fast judgement · Held for a closer look");
    expect(chain).toContain("Financial crime lead approved");
    expect(chain).toContain("deep review · Deep review: The record is consistent.");
    expect(chain.indexOf("held it")).toBeLessThan(chain.indexOf("Financial crime lead approved"));
    expect(chain.indexOf("Financial crime lead approved")).toBeLessThan(chain.indexOf("Decision approved"));
  });

  it("shows a send-back to the agent and the decision after re-assessment", async () => {
    details["/api/workflows/bapp-evt-11"] = { workflow: { payload: { decisions: [
      { persona_role: "financial_crime_lead", verdict: "send_back", decided_by: "llm",
        judgement: { summary: "Sent back to the agent: the reasoning contradicts the record." } },
      { persona_role: "fraud_decision_manager", verdict: "approve", decided_by: "laya", round: 1,
        judgement: { summary: "Approved after reading the agent's reasoning: no concerns found." } },
    ] } } };
    renderBank({ events: [ROUTINE, ...APPROVED_TRACE, ...APPROVED_OUTCOME] });
    const strip = screen.getByTestId("banking-intervention");
    expect(await within(strip).findByText("Financial crime lead sent it back to the agent")).toBeTruthy();
    expect(within(strip).getByText("Fraud decision manager approved after re-assessment")).toBeTruthy();
  });

  it("asks the world for mule activity when the bank screens payments", () => {
    const onRunScenario = vi.fn(async () => {});
    renderBank({ onRunScenario, state: { ...STATE, screening: { payments_screened: 4, payments_flagged: 1 } } as WorldState });
    fireEvent.click(screen.getByRole("button", { name: "Mule activity detected" }));
    expect(onRunScenario).toHaveBeenCalledWith("mule-activity");
    expect(fetch).not.toHaveBeenCalledWith(expect.stringContaining("inject-burst"), expect.anything());
  });

  it("shows what the bank noticed and how customers reacted", () => {
    renderBank({ state: { ...STATE, screening: {
      payments_screened: 40, payments_flagged: 3, mule_cases_open: 1, mule_cases_decided: 2,
      recent_flags: [{ payment_id: "SYN-PAY-N00007", beneficiary_id: "SYN-BENE-002", reference: "Release fee to unlock withdrawal",
        pattern: "unlock_fee", lead: 1, screened_by: "laya", amount_gbp: 900 }],
      customer_reactions: { accepts: 2, chases: 1, complains: 1 },
    } } as WorldState });
    expect(screen.getByTestId("noticed-counts").textContent).toBe("3 flagged of 40 screened · 1 mule cases open · 2 decided");
    expect(screen.getByTestId("customer-reactions").textContent).toBe("Customers: 2 accepted · 1 chased · 1 complained");
    expect(screen.getByTestId("flag-SYN-PAY-N00007").textContent).toContain("unlock fee · read by Laya");
  });

  it("hides the noticed panel when the bank does not screen", () => {
    renderBank();
    expect(screen.queryByTestId("bank-noticed")).toBeNull();
  });

  it("names who approved when the decision was handed up", () => {
    const escalated = APPROVED_OUTCOME.map((e) => e.type === "responder.decided"
      ? { ...e, payload: { ...e.payload, command: { payload: { option_id: "SYN-APP-OPTION-REIMBURSE-CAPPED", value_gbp: 85_000, persona: "financial_crime_lead" } } } }
      : e);
    renderBank({ events: [ROUTINE, ...APPROVED_TRACE, ...escalated] });
    expect(screen.getByTestId("banking-intervention").textContent).toContain(
      "Reimburse to the £85k cap · £85,000 · by Financial crime lead",
    );
  });

  it("reads a persona's decline as a decline, not a refusal by authority", () => {
    const declined = REFUSED_TRACE.map((e) => e.type === "responder.deferred"
      ? { ...e, payload: { ...e.payload, reasoning: "financial crime lead declined to approve: Deep review: the reasoning contradicts the record." } }
      : e);
    renderBank({ events: [ROUTINE, ...declined] });
    expect(screen.getByTestId("claim-outcome-SYN-CLAIM-0033").textContent).toBe("Declined by Financial crime lead");
    const chain = screen.getByTestId("banking-intervention").textContent ?? "";
    expect(chain).toContain("Financial crime lead declined");
    expect(chain).toContain("Claim declined");
    expect(chain).not.toContain("Refused by authority");
  });

  it("shows on each recent case who decided and how", async () => {
    workflows = [{
      id: "BMUL-0002", type: "mule-account-investigation", status: "completed", currentPhase: "Verify Disposition", createdAt: 10, metadata: {},
      payload: { decisions: [{ persona_role: "financial_crime_lead", verdict: "approve", decided_by: "laya", judgement: { summary: "Approved." } }] },
    }];
    renderBank();
    expect((await screen.findByTestId("judged-BMUL-0002")).textContent).toBe("Financial crime lead · fast judgement");
  });

  it("shows no decisions waiting when the queue is empty", () => {
    renderBank();
    expect(screen.getByTestId("decisions-waiting").textContent).toBe("0");
    expect(screen.queryByTestId("pending-decisions")).toBeNull();
  });

  it("hides routine events by default and shows them after toggling", () => {
    renderBank();
    const journal = screen.getByTestId("banking-journal");
    expect(within(journal).queryByText("banking.payment.settled")).toBeNull();
    expect(within(journal).getByText("responder.deferred")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Show routine activity" }));

    expect(within(journal).getByText("banking.payment.settled")).toBeTruthy();
  });
});

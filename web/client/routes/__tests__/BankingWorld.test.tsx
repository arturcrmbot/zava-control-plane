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
let posted: Record<string, unknown> = {};
let statuses: Record<string, number> = {};

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
  posted = {};
  statuses = {};
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const path = String(url);
    const body = path === "/api/workflows" ? workflows
      : path.startsWith("/api/workflows/") ? details[path] ?? {}
      : path.startsWith("/api/simulator/inject-burst") ? { ok: true }
      : path in posted ? posted[path]
      : queue;
    return new Response(JSON.stringify(body), { status: statuses[path] ?? 200 });
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
    expect(chain).toContain("quick check · Held for a closer look");
    expect(chain).toContain("Financial crime lead approved");
    expect(chain).toContain("closer review · The record is consistent.");
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
    expect(screen.getByTestId("customer-reactions").textContent).toBe("After a claim decision: 2 accepted it · 1 chased us · 1 complained");
    expect(screen.getByTestId("flag-SYN-PAY-N00007").textContent).toContain("unlock fee · £900");
    expect(screen.getByTestId("bank-noticed").textContent).not.toContain("Laya");
  });

  it("tells the living world in the bank's words and names Laya only in the folded explainer", () => {
    const decision = (kind: string, title: string, steps: unknown[], outcome: string) => ({ t: 1, when: "Friday night", kind, who: "x", profile: "Liam Chen, 21, a student.", title, steps, outcome });
    renderBank({ state: { ...STATE, sim_time: 1440 * 4 + 19 * 60 + 5, screening: { payments_screened: 90, payments_flagged: 3 },
      reimbursement_evaluations: [{ id: "E1", claim_id: "C1", reimbursed_gbp: 900 }, { id: "E2", claim_id: "C2", reimbursed_gbp: 0 }],
      life: {
        people: 214, payments: 945, scams_tried: 54, scams_paid: 18, scams_stopped: 18, scams_ignored: 18, calls: 1, joined: 14, left: 0, life_events: 5,
        lost_gbp: 23_450, unreported_count: 2, unreported_gbp: 3_100,
        unreported: [{ name: "Nadia Shah", amount_gbp: 2_200, scam: "fake bank fraud team", hours_ago: 3.4 }, { name: "Olu Wright", amount_gbp: 900, scam: "romance", hours_ago: 0.5 }],
        decided_by_laya: 300, decided_by_rules: 20, laya_share: 0.94, laya_avg_ms: 88, cases_opened: 2, cases_per_hour: 10,
        decisions: [decision("spend", "Liam Chen, Friday night", [{ by: "laya", question: "What is Liam most likely to spend money on right now?", chose: "eat_out", ms: 71,
          options: [{ id: "eat_out", label: "Eating out or ordering a takeaway", p: 0.48 }, { id: "treat", label: "A night out", p: 0.21 }] }], "paid Lucky Noodle £22: \"Takeaway\""),
          { ...decision("spend", "Rhys Singh decides what to spend on", [{ by: "laya", question: "What is Rhys most likely to spend money on right now?", chose: "groceries",
            options: [{ id: "eat_out", label: "Eating out", p: 0.43 }, { id: "shop_online", label: "Buying something online", p: 0.19 },
              { id: "bills", label: "Paying a household bill", p: 0.13 }, { id: "groceries", label: "Doing the food shopping", p: 0.1 }] }], "paid Market Basket £16"), t: 2 }],
        scam_decisions: [decision("scam", "Crew Harbour tried a romance scam on Dorothy Walsh", [
          { by: "laya", question: "Which scam would most likely work on Dorothy?", chose: "romance", options: [{ id: "romance", label: "A fake online romance asking for money", p: 0.6 }] },
          { by: "code", question: "What Dorothy does, after the bank's warning", chose: "pay", options: [{ id: "pay", label: "Do what the message asks and send the money", p: 0.62 }] },
        ], "fell for a romance scam and sent £900 despite the bank's warning")],
        unknown_to_bank: [{ name: "Gareth Rossi", circumstance: "just out of hospital after a stroke" }],
        crews: { "Crew Harbour": { romance: { tried: 2, paid: 1 } } },
        stories: [{ t: 2, when: "Friday night", who: "Joan Chen", text: "Joan Chen called Zava Bank before paying a tax office penalty scam", by: "laya", kind: "scam" }],
        feed: [],
      } } as WorldState });
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Zava Bank");
    expect(screen.getByTestId("world-clock").textContent).toBe("Friday 19:05");
    const today = screen.getByTestId("bank-today");
    expect(today.textContent).toContain("214customers");
    expect(today.textContent).toContain("£23,450lost by 18 customers");
    expect(today.textContent).toContain("18 checked with us first · 18 ignored it");
    expect(today.textContent).toContain("3 payments flagged by screening · 2 losses not reported yet");
    expect(today.textContent).toContain("2claims decided");
    expect(today.textContent).toContain("£900 refunded · 0 waiting for a manager");
    const decisions = screen.getByTestId("customer-decisions");
    const scam = within(decisions).getByTestId("decision-scam");
    expect(scam.textContent).toContain("Crew Harbour tried a romance scam on Dorothy Walsh");
    expect(scam.textContent).toContain("What Dorothy does, after the bank's warning");
    const spend = within(decisions).getAllByTestId("decision-spend")[0];
    expect(spend.textContent).toContain("What is Liam most likely to spend money on right now?");
    expect(spend.textContent).toContain("✓ Eating out or ordering a takeaway");
    expect(spend.textContent).toContain("48%");
    expect(spend.textContent).toContain("→ paid Lucky Noodle £22");
    // An unlikely choice is still shown, in place of the third likeliest.
    const unlikely = within(decisions).getAllByTestId("decision-spend")[1];
    expect(unlikely.textContent).toContain("✓ Doing the food shopping");
    expect(unlikely.textContent).not.toContain("Paying a household bill");
    expect(screen.getByTestId("unreported-total").textContent).toBe("2 customers · £3,100");
    expect(screen.getByTestId("unreported-losses").textContent).toContain("Nadia Shah · fake bank fraud team£2,200 · 3 h ago");
    expect(screen.getByTestId("unknown-to-bank").textContent).toContain("Gareth Rossi just out of hospital after a stroke");
    expect(screen.getByTestId("crew-board").textContent).toContain("romance 1/2");
    expect(screen.getByTestId("life-stories").textContent).toContain("Joan Chen called Zava Bank before paying");
    expect((screen.getByTestId("bank-infrastructure") as HTMLDetailsElement).open).toBe(false);
    expect(screen.queryByTestId("bank-stat-mtm")).toBeNull();
    expect(screen.queryByTestId("banking-objective")).toBeNull();
    // Laya is named once, in the folded explainer, with what it has done.
    const about = screen.getByTestId("about-simulation") as HTMLDetailsElement;
    expect(about.open).toBe(false);
    expect(screen.getByTestId("about-numbers").textContent).toContain("320 customer choices, 94% by Laya (about 88 ms each)");
    const page = screen.getByTestId("banking-world-route").textContent ?? "";
    expect(page.replace(about.textContent ?? "", "")).not.toMatch(/Laya| ms\b|tokens/);
  });

  it("holds a customer's story still while the pointer is on it", () => {
    const scam = (who: string, t: number) => ({ t, when: "Monday night", kind: "scam", who, profile: `${who}, 46.`, title: `Crew North tried a tax office penalty scam on ${who}`,
      steps: [{ by: "laya", question: `Which scam would most likely work on ${who}?`, chose: "", options: [{ id: "tax", label: "A threatening message from the tax office", p: 0.6 }] }],
      outcome: "fell for a tax office penalty scam" });
    const living = (who: string, t: number) => ({ ...STATE, life: { people: 200, scam_decisions: [scam(who, t)], decisions: [] } }) as WorldState;
    const { rerender, props } = renderBank({ state: living("Priya Jones", 1) });
    const panel = screen.getByTestId("customer-decisions");
    fireEvent.mouseEnter(panel);
    rerender(<BankingWorld {...props} state={living("Sian Shah", 2)} />);
    expect(panel.textContent).toContain("Priya Jones");
    expect(panel.textContent).not.toContain("Sian Shah");
    expect(screen.getByTestId("decisions-held").textContent).toBe("held while you read");
    fireEvent.mouseLeave(panel);
    expect(panel.textContent).toContain("Sian Shah");
    expect(screen.queryByTestId("decisions-held")).toBeNull();
  });

  it("names the claimant on the latest claim when the world knows who they are", () => {
    renderBank({ events: [ROUTINE, ...APPROVED_TRACE], state: { ...STATE, life: { people: 200, claimants: { "SYN-CUST-0007": "Rosa Taylor" } } } as WorldState });
    const strip = screen.getByTestId("banking-intervention");
    expect(strip.textContent).toContain("The latest claim, step by step");
    expect(strip.textContent).toContain("Rosa Taylor");
    expect(strip.textContent).not.toContain("SYN-CUST-0007");
  });

  it("shows what the manager checked in the agent's reasoning for the case on screen", async () => {
    details["/api/workflows/bapp-evt-11"] = { workflow: { payload: {
      decisions: [{ persona_role: "fraud_decision_manager", verdict: "hold", decided_by: "laya", judgement: {
        summary: "Held for a closer look.", laya_ms: 154, concerns: ["the agent's reasoning says there is no vulnerability marker, but the record shows one"],
        readings: [{ id: "says_no_marker", question: "Does the text say there is no vulnerability flag?", p_yes: 0.94, lead: 0.88, clear: true }] } }],
    } } };
    renderBank({ events: [ROUTINE, ...APPROVED_TRACE, ...APPROVED_OUTCOME], state: { ...STATE, life: { people: 200, decisions: [], scam_decisions: [] } } });
    const panel = await screen.findByTestId("persona-readings");
    expect(panel.textContent).toContain("What the fraud decision manager checked before deciding");
    expect(panel.textContent).toContain("Does the text say there is no vulnerability flag?");
    expect(panel.textContent).toContain("Yes 94%");
    expect(panel.textContent).toContain("Found: the agent's reasoning says there is no vulnerability marker");
    expect(panel.textContent).toContain("Decision: Held for a closer look.");
    expect(panel.textContent).not.toMatch(/Laya|154/);
  });

  it("hides the noticed panel when the bank does not screen", () => {
    renderBank();
    expect(screen.queryByTestId("bank-noticed")).toBeNull();
  });

  it("reports a customer's call about a payment and shows the advisory reading", async () => {
    posted["/api/world/customer-calls"] = { ok: true, claim_id: "SYN-CLAIM-C001",
      reading: { scam_type: "bank_impersonation", scam_lead: 0.8, cues: ["bereavement"], read_by: "laya" } };
    renderBank();
    const panel = screen.getByTestId("customer-call");
    fireEvent.change(within(panel).getByLabelText("Payment"), { target: { value: "SYN-PAY-0100" } });
    fireEvent.change(within(panel).getByLabelText("What the customer says"), { target: { value: "My bank's fraud team told me to move my savings." } });
    fireEvent.click(within(panel).getByRole("button", { name: "Report the call" }));
    const result = await within(panel).findByTestId("customer-call-result");
    expect(result.textContent).toBe("Claim SYN-CLAIM-C001 raised · first impression: bank impersonation · noted: bereavement. The evidence decides.");
    const call = (fetch as unknown as { mock: { calls: [string, RequestInit?][] } }).mock.calls.find(([url]) => url === "/api/world/customer-calls");
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ payment_id: "SYN-PAY-0100", statement: "My bank's fraud team told me to move my savings." });
  });

  it("asks the persona how it would judge the case with one thing changed", async () => {
    details["/api/workflows/bapp-evt-11"] = { workflow: { payload: {
      decisions: [{ persona_role: "fraud_decision_manager", verdict: "approve", decided_by: "laya", judgement: { summary: "Approved." } }],
      hitl_context: { persona: "fraud_decision_manager", ranking: { reasoning: "No vulnerability flag is present." },
        observation: { claim: { vulnerability_flag: false } } },
    } } };
    posted["/api/judgement/what-if"] = { ok: true, decision: "escalate",
      summary: "Held for a closer look: the agent's reasoning says there is no vulnerability marker, but the record shows one." };
    renderBank({ events: [ROUTINE, ...APPROVED_TRACE, ...APPROVED_OUTCOME] });
    const panel = await screen.findByTestId("ask-persona");
    expect((within(panel).getByLabelText("The agent's reasoning") as HTMLTextAreaElement).value).toBe("No vulnerability flag is present.");
    fireEvent.click(within(panel).getByRole("checkbox"));
    fireEvent.click(within(panel).getByRole("button", { name: "Ask" }));
    const answer = await within(panel).findByTestId("ask-persona-answer");
    expect(answer.textContent).toContain("Fraud decision manager would hand it up: Held for a closer look");
    const call = (fetch as unknown as { mock: { calls: [string, RequestInit?][] } }).mock.calls.find(([url]) => url === "/api/judgement/what-if");
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ workflow_id: "bapp-evt-11", vulnerable: true });
  });

  it("files a call on the payment the presenter chose while new payments settle", async () => {
    posted["/api/world/customer-calls"] = { ok: true, claim_id: "SYN-CLAIM-C001", reading: null };
    const { rerender, props } = renderBank();
    const panel = screen.getByTestId("customer-call");
    const report = within(panel).getByRole("button", { name: "Report the call" }) as HTMLButtonElement;
    fireEvent.change(within(panel).getByLabelText("What the customer says"), { target: { value: "I was scammed." } });
    expect(report.disabled).toBe(true); // nothing is chosen for the presenter
    fireEvent.change(within(panel).getByLabelText("Payment"), { target: { value: "SYN-PAY-0100" } });
    const newer = { ...STATE, recent_settlements: [{ payment_id: "SYN-PAY-0200", rail_id: "SYN-RAIL-FPS", amount_gbp: 99, sim_time: 430, event_id: "evt-2" }] };
    rerender(<BankingWorld {...props} state={newer} />);
    const select = within(panel).getByLabelText("Payment") as HTMLSelectElement;
    const offered = () => [...select.options].map((o) => o.value);
    expect(select.value).toBe("SYN-PAY-0100");
    expect(offered()).toEqual(["", "SYN-PAY-0100"]); // a steady list until the presenter refreshes it
    fireEvent.click(within(panel).getByRole("button", { name: "Refresh payments" }));
    expect(offered()).toEqual(["", "SYN-PAY-0100", "SYN-PAY-0200"]); // the chosen payment stays
    fireEvent.click(report);
    await within(panel).findByTestId("customer-call-result");
    const call = (fetch as unknown as { mock: { calls: [string, RequestInit?][] } }).mock.calls.find(([url]) => url === "/api/world/customer-calls");
    expect(JSON.parse(String(call?.[1]?.body)).payment_id).toBe("SYN-PAY-0100");
  });

  it("still asks the persona after the gate has closed", async () => {
    details["/api/workflows/bapp-evt-11"] = { workflow: { payload: {
      decisions: [{ persona_role: "fraud_decision_manager", verdict: "approve", decided_by: "laya", judgement: { summary: "Approved." } }],
      judged_gate_context: { persona: "fraud_decision_manager", ranking: { reasoning: "No vulnerability flag is present." },
        observation: { claim: { vulnerability_flag: false } } },
    } } };
    renderBank({ events: [ROUTINE, ...APPROVED_TRACE, ...APPROVED_OUTCOME] });
    const panel = await screen.findByTestId("ask-persona");
    expect((within(panel).getByLabelText("The agent's reasoning") as HTMLTextAreaElement).value).toBe("No vulnerability flag is present.");
  });

  it("says why the persona could not be asked", async () => {
    details["/api/workflows/bapp-evt-11"] = { workflow: { payload: {
      decisions: [{ persona_role: "fraud_decision_manager", verdict: "approve", decided_by: "laya", judgement: { summary: "Approved." } }],
      hitl_context: { persona: "fraud_decision_manager", ranking: { reasoning: "No vulnerability flag is present." },
        observation: { claim: { vulnerability_flag: false } } },
    } } };
    statuses["/api/judgement/what-if"] = 422;
    posted["/api/judgement/what-if"] = { detail: [{ msg: "String should have at most 8000 characters" }] };
    renderBank({ events: [ROUTINE, ...APPROVED_TRACE, ...APPROVED_OUTCOME] });
    const panel = await screen.findByTestId("ask-persona");
    fireEvent.change(within(panel).getByLabelText("The agent's reasoning"), { target: { value: "A much longer reasoning." } });
    fireEvent.click(within(panel).getByRole("button", { name: "Ask" }));
    const answer = await within(panel).findByTestId("ask-persona-answer");
    expect(answer.textContent).toBe("The question was not accepted: String should have at most 8000 characters");
    const call = (fetch as unknown as { mock: { calls: [string, RequestInit?][] } }).mock.calls.find(([url]) => url === "/api/judgement/what-if");
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ workflow_id: "bapp-evt-11", reasoning: "A much longer reasoning." });
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
    expect((await screen.findByTestId("judged-BMUL-0002")).textContent).toBe("Financial crime lead approved");
  });

  it("names the customer and the amount on a recent case in the living world", async () => {
    workflows = [{
      id: "bapp-evt-00000565", type: "app-fraud-reimbursement", status: "completed", currentPhase: "Verify Reimbursement Outcome", createdAt: 10, metadata: {},
      payload: { observation: { claim: { id: "SYN-CLAIM-C001", customer_id: "SYN-CUST-2361", amount_gbp: 2510 } },
        decisions: [{ persona_role: "fraud_decision_manager", verdict: "approve", decided_by: "laya", judgement: { summary: "Approved." } }] },
    }];
    renderBank({ state: { ...STATE, life: { people: 200, claimants: { "SYN-CUST-2361": "Priya Jones" } } } as WorldState });
    expect((await screen.findByTestId("case-who-bapp-evt-00000565")).textContent).toBe(" · Priya Jones · £2,510");
    expect(screen.getByTestId("judged-bapp-evt-00000565").textContent).toBe("Fraud decision manager approved");
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

// @vitest-environment jsdom
// web/client/routes/__tests__/TelcoWorld.test.tsx
//
// Proves the scenario-aware /world surface renders the telco cell-site floor
// from ACTUAL actors in a mocked useWorldSimulation:
//   - state.scenario === "telco" swaps the support floor for TelcoWorld
//   - real CellSite IDs land in their region columns; the failed site is
//     marked as the incident and its neighbours are known
//   - real NetworkSession IDs land in the degraded / rerouted lanes with the
//     TRUE totals even when the DOM token list is capped
//   - the Durable intervention strip renders the real network-anomaly trace
//     and the causal steps (anomaly → decided → rerouted → recovered)
//   - the single "Fail site" control invokes injectSiteFailure
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, within, cleanup, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type {
  UseWorldSimulationResult,
  WorldEvent,
  WorldSession,
  WorldSite,
  WorldState,
} from "@client/hooks/useWorldSimulation";

const { mockUseWorld } = vi.hoisted(() => ({ mockUseWorld: vi.fn() }));
vi.mock("@client/hooks/useWorldSimulation", () => ({
  useWorldSimulation: mockUseWorld,
}));
vi.mock("@client/hooks/useRuntimeManifest", () => ({
  useRuntimeManifest: () => ({
    loading: false,
    error: null,
    manifest: {
      vertical: { display_name: "Telco" },
      world: "telco",
      ui: { lenses: ["telco-network"] },
    },
  }),
}));

import World from "../World";

function ev(
  seq: number,
  type: string,
  actor_id: string | null,
  target_id: string | null,
  cause_event_id: string | null,
  trace_id: string,
  payload: Record<string, unknown> = {},
): WorldEvent {
  return { seq, event_id: `E-${seq}`, sim_time: seq, type, actor_id, target_id, cause_event_id, trace_id, payload };
}

const TRACE = "network-anomaly-SITE-01-100";

const SITES: WorldSite[] = [
  { id: "SITE-01", region: "north", status: "failed", capacity_mbps: 600, traffic_mbps: 0, utilization: 0, packet_loss_pct: 0, latency_ms: 20, session_count: 0, neighbor_ids: ["SITE-02", "SITE-03", "SITE-04"] },
  { id: "SITE-02", region: "north", status: "healthy", capacity_mbps: 600, traffic_mbps: 300, utilization: 0.5, packet_loss_pct: 0.4, latency_ms: 21, session_count: 30, neighbor_ids: ["SITE-01", "SITE-03", "SITE-05"] },
  { id: "SITE-03", region: "north", status: "healthy", capacity_mbps: 600, traffic_mbps: 420, utilization: 0.7, packet_loss_pct: 0.5, latency_ms: 22, session_count: 42, neighbor_ids: ["SITE-01", "SITE-02", "SITE-06"] },
  { id: "SITE-04", region: "east", status: "healthy", capacity_mbps: 600, traffic_mbps: 200, utilization: 0.33, packet_loss_pct: 0.3, latency_ms: 19, session_count: 20, neighbor_ids: ["SITE-05", "SITE-06", "SITE-01"] },
];

function session(id: string, status: WorldSession["status"], site: string, origin: string, kind: WorldSession["kind"] = "data"): WorldSession {
  return { id, subscriber_id: `SUB-${id.slice(-4)}`, site_id: site, origin_site_id: origin, kind, demand_mbps: 2, status };
}

// 3 degraded (all origin SITE-01), 26 rerouted (> TOKEN_CAP to prove capping),
// and a couple of active elsewhere.
const DEGRADED = [
  session("SESSION-0001", "degraded", "SITE-01", "SITE-01", "voice"),
  session("SESSION-0002", "degraded", "SITE-01", "SITE-01"),
  session("SESSION-0003", "degraded", "SITE-01", "SITE-01"),
];
const REROUTED: WorldSession[] = Array.from({ length: 26 }, (_, i) =>
  session(`SESSION-1${String(i).padStart(3, "0")}`, "rerouted", "SITE-02", "SITE-01"),
);
const ACTIVE = [session("SESSION-9001", "active", "SITE-04", "SITE-04")];
const SESSIONS: WorldSession[] = [...DEGRADED, ...REROUTED, ...ACTIVE];

const EVENTS: WorldEvent[] = [
  ev(80, "site.failed", "SITE-01", "region:north", null, "network-incident-SITE-01-100", { region: "north", affected_session_count: 3 }),
  ev(81, "session.degraded", "SESSION-0001", "SITE-01", "E-80", "network-incident-SITE-01-100"),
  ev(90, "sensor.tripped", "sensor:network_anomaly", "SITE-01", "E-80", TRACE, { actor_ids: ["SESSION-0001"], measurements: { site_id: "SITE-01", region: "north", affected_session_count: 3 } }),
  ev(91, "responder.requested", null, null, "E-90", TRACE),
  ev(92, "responder.decided", null, null, "E-91", TRACE, { instance_id: "abc123def456xyz" }),
  ev(93, "command.accepted", "network_incident", "SITE-01", null, TRACE),
  ev(94, "session.rerouted", "SESSION-1000", "SITE-02", "E-93", TRACE, { from_site_id: "SITE-01", to_site_id: "SITE-02" }),
  ev(95, "session.rerouted", "SESSION-1001", "SITE-03", "E-93", TRACE, { from_site_id: "SITE-01", to_site_id: "SITE-03" }),
  ev(96, "site.recovered", "SITE-01", null, "E-93", TRACE, { rerouted_session_count: 26 }),
];

const TELCO_STATE: WorldState = {
  enabled: true,
  scenario: "telco",
  seed: 42,
  status: "running",
  sim_time: 100,
  latest_seq: 96,
  sites: SITES,
  sessions: SESSIONS,
  subscribers: [{ id: "SUB-0001", home_site_id: "SITE-01", tier: "standard", session_count: 1 }],
  accounts: [
    { id: "ACC-00001", subscriber_id: "SUB-0001", segment: "business", vulnerable: false, approval_required: false, total_credits: 5, notification_ids: ["NOT-1"], credit_ids: ["CRD-1"] },
  ],
  subscriptions: [
    { id: "SUBS-00001", account_id: "ACC-00001", subscriber_id: "SUB-0001", site_id: "SITE-01", product: "5g-premium", status: "active" },
  ],
  orders: [
    { id: "ORD-00001", account_id: "ACC-00001", product: "fiber-1gb", requested_site_id: "SITE-02", status: "pending" },
  ],
  notifications: [
    { id: "NOT-1", account_id: "ACC-00001", channel: "sms", message: "Service restored", trace_id: TRACE },
  ],
  credits: [
    { id: "CRD-1", account_id: "ACC-00001", amount: 5, trace_id: TRACE, authority_approved: true },
  ],
  assets: [
    { id: "AST-SITE-01-radio-unit", site_id: "SITE-01", kind: "radio-unit", health: 0.41, temperature_c: 67, load: 0.9, failure_probability: 0.72, status: "degraded", risk_band: "high" },
  ],
  work_orders: [
    { id: "WO-00001", site_id: "SITE-01", asset_id: "AST-SITE-01-radio-unit", kind: "repair", priority: 1, required_skill: "radio-unit", required_spare: "radio-unit", due_at: 120, status: "open", technician_id: null },
  ],
  technicians: [
    { id: "TECH-NORTH-01", region: "north", skills: ["radio-unit"], status: "prestaged", assigned_work_order_id: null },
  ],
  spare_stocks: [
    { id: "SPARE-NORTH-RADIO-UNIT", region: "north", part_kind: "radio-unit", quantity: 0, reorder_point: 5 },
  ],
  care_tickets: [
    { id: "TKT-000001", account_id: "ACC-00001", subscription_id: "SUBS-00001", incident_trace_id: TRACE, category: "network_outage", severity: "high", status: "open", root_cause: null },
  ],
  experience_episodes: [
    { id: "EXP-000001", account_id: "ACC-00001", source_trace_id: TRACE, kind: "service_outage", impact_score: 0.7, occurred_at: 80 },
  ],
  retention_offers: [
    { id: "RET-000001", account_id: "ACC-00001", reason: "Service recovery", value_gbp: 75, offer_kind: "service_recovery_bundle", status: "issued" },
  ],
  customer_impact: { affected_account_count: 1, notified_account_count: 1, credited_account_count: 1, account_ids: ["ACC-00001"] },
  objectives: [
    {
      id: "obj-E-60", type: "network_service_recovery", trace_id: TRACE, owner_function: "network_incident",
      priority: 0, status: "evaluating", created_at: 60, deadline: null,
      evidence_event_ids: ["E-60"], allowed_command_types: ["reroute_sessions"],
      claimed_by: "network_incident",
    },
  ],
};

function hook(over: Partial<UseWorldSimulationResult> = {}): UseWorldSimulationResult {
  return {
    state: TELCO_STATE,
    events: EVENTS,
    loading: false,
    error: null,
    injectSurge: vi.fn(async () => {}),
    injectSiteFailure: vi.fn(async () => {}),
    runScenario: vi.fn(async () => {}),
    runReferenceProcess: vi.fn(async () => {}),
    ...over,
  };
}

function renderWorld() {
  return render(<MemoryRouter><World /></MemoryRouter>);
}

beforeEach(() => {
  mockUseWorld.mockReset();
  mockUseWorld.mockReturnValue(hook());
});
afterEach(cleanup);

describe("TelcoWorld route", () => {
  it("swaps the support floor for the telco cell-site floor on scenario=telco", () => {
    renderWorld();
    expect(screen.getByTestId("telco-world-route")).toBeTruthy();
    // The support ticket floor must NOT render.
    expect(screen.queryByTestId("world-route")).toBeNull();
    expect(screen.queryByTestId("lane-waiting")).toBeNull();
  });

  it("renders real CellSite IDs in their region columns", () => {
    renderWorld();
    const north = screen.getByTestId("region-north");
    expect(within(north).getByTestId("site-SITE-01")).toBeTruthy();
    expect(within(north).getByTestId("site-SITE-02")).toBeTruthy();
    expect(within(north).getByTestId("site-SITE-03")).toBeTruthy();
    const east = screen.getByTestId("region-east");
    expect(within(east).getByTestId("site-SITE-04")).toBeTruthy();
  });

  it("marks the failed site as the incident and reports its status", () => {
    renderWorld();
    const failed = screen.getByTestId("site-SITE-01");
    expect(failed.getAttribute("data-incident")).toBe("true");
    expect(failed.getAttribute("data-status")).toBe("failed");
    // A healthy neighbour is not the incident.
    expect(screen.getByTestId("site-SITE-02").getAttribute("data-incident")).toBe("false");
  });

  it("lands real degraded/rerouted session IDs in their lanes with TRUE totals", () => {
    renderWorld();
    const degraded = screen.getByTestId("session-lane-degraded");
    expect(within(degraded).getByTestId("session-SESSION-0001")).toBeTruthy();
    expect(within(degraded).getByTestId("session-SESSION-0003")).toBeTruthy();
    expect(screen.getByTestId("session-count-degraded").textContent).toBe("3");

    // Rerouted lane is capped in the DOM but the count is the TRUE total (26).
    const rerouted = screen.getByTestId("session-lane-rerouted");
    expect(within(rerouted).getByTestId("session-SESSION-1000")).toBeTruthy();
    expect(screen.getByTestId("session-count-rerouted").textContent).toBe("26");
    const tokens = within(rerouted).getAllByTestId(/^session-SESSION-1/);
    expect(tokens.length).toBeLessThanOrEqual(24);
    expect(within(rerouted).getByText("+2")).toBeTruthy();
  });

  it("renders the Durable causal chain with the real network-anomaly trace", () => {
    renderWorld();
    const strip = screen.getByTestId("telco-intervention");
    expect(within(strip).getByText(TRACE)).toBeTruthy();
    expect(within(strip).getByText("Anomaly detected")).toBeTruthy();
    expect(within(strip).getByText("Durable decided")).toBeTruthy();
    expect(within(strip).getByText("2 sessions rerouted")).toBeTruthy();
    expect(within(strip).getByText("Site recovered")).toBeTruthy();
  });

  it("renders the compact objective status row from the snapshot", () => {
    renderWorld();
    const strip = screen.getByTestId("telco-objective");
    expect(within(strip).getByTestId("telco-objective-status").textContent).toMatch(/evaluating/i);
    expect(within(strip).getByText(/network_service_recovery/)).toBeTruthy();
    expect(within(strip).getByText(/network_incident/)).toBeTruthy();
  });

  it("invokes injectSiteFailure from the single Fail site control", () => {
    const injectSiteFailure = vi.fn(async () => {});
    mockUseWorld.mockReturnValue(hook({ injectSiteFailure }));
    renderWorld();
    fireEvent.click(screen.getByTestId("inject-site-failure"));
    expect(injectSiteFailure).toHaveBeenCalledTimes(1);
  });

  it("runs a deterministic interconnected scenario", () => {
    const runScenario = vi.fn(async () => {});
    mockUseWorld.mockReturnValue(hook({ runScenario }));
    renderWorld();

    fireEvent.click(screen.getByRole("button", { name: "Storm Cascade" }));

    expect(runScenario).toHaveBeenCalledWith("storm-cascade");
  });

  it("renders field, customer impact, order, and control lenses from snapshot data", () => {
    renderWorld();

    fireEvent.click(screen.getByRole("button", { name: "Field Operations" }));
    expect(screen.getByText("AST-SITE-01-radio-unit")).toBeTruthy();
    expect(screen.getByText("WO-00001")).toBeTruthy();
    expect(screen.getByText("TECH-NORTH-01")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Customer Impact" }));
    expect(screen.getByText("ACC-00001")).toBeTruthy();
    expect(screen.getByText(/£5 credit/)).toBeTruthy();
    expect(screen.getByText("TKT-000001")).toBeTruthy();
    expect(screen.getByText("RET-000001")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Orders" }));
    expect(screen.getByText("ORD-00001")).toBeTruthy();
    expect(screen.getByText(/fiber-1gb/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Control" }));
    expect(screen.getByText(TRACE)).toBeTruthy();
    expect(screen.getByText(/care.completed|site.recovered/)).toBeTruthy();
  });

  it("keeps customer impact focused on six priority accounts", () => {
    const accounts = Array.from({ length: 20 }, (_, index) => ({
      id: `ACC-${String(index + 1).padStart(5, "0")}`,
      subscriber_id: `SUB-${String(index + 1).padStart(5, "0")}`,
      segment: index === 0 ? "priority_business" : "consumer",
      vulnerable: index === 1,
      approval_required: false,
      total_credits: index < 2 ? 20 : 0,
      notification_ids: index < 2 ? [`NOT-${index + 1}`] : [],
      credit_ids: index < 2 ? [`CRD-${index + 1}`] : [],
    }));
    mockUseWorld.mockReturnValue(hook({
      state: {
        ...TELCO_STATE,
        accounts,
        customer_impact: {
          affected_account_count: 20,
          notified_account_count: 2,
          credited_account_count: 2,
          account_ids: accounts.map((account) => account.id),
        },
      },
    }));
    renderWorld();

    fireEvent.click(screen.getByRole("button", { name: "Customer Impact" }));

    expect(screen.getAllByTestId("customer-account-card")).toHaveLength(6);
    expect(screen.getByText("Showing 6 of 20 impacted accounts")).toBeTruthy();
    expect(screen.getByText("TKT-000001")).toBeTruthy();
    expect(screen.getByText("RET-000001")).toBeTruthy();
  });

  it("submits a real demo service order from the Orders lens", async () => {
    const fetchMock = vi.fn(async () => new Response(
      JSON.stringify({ ok: true, order_id: "ORD-00002" }),
      { status: 200 },
    ));
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    renderWorld();
    fireEvent.click(screen.getByRole("button", { name: "Orders" }));

    fireEvent.click(screen.getByRole("button", { name: "Submit demo order" }));

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/world/service-orders",
      expect.objectContaining({ method: "POST" }),
    );
  });
});

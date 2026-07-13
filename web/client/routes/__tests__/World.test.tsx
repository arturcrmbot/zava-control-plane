// @vitest-environment jsdom
// web/client/routes/__tests__/World.test.tsx
//
// The route renders ACTUAL actors from a mocked useWorldSimulation and proves:
//   - real ticket/worker IDs land in the correct lanes and groups
//   - the Durable intervention strip renders the real trace + reallocated IDs
//   - the single control invokes injectSurge
//   - loading / disabled / error states are explicit
//   - clicking an actor filters the journal
//   - no aggregate-only WorldSignalsPanel is embedded
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, within, cleanup, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type {
  UseWorldSimulationResult,
  WorldEvent,
  WorldState,
} from "@client/hooks/useWorldSimulation";

const { mockUseWorld } = vi.hoisted(() => ({ mockUseWorld: vi.fn() }));
vi.mock("@client/hooks/useWorldSimulation", () => ({
  useWorldSimulation: mockUseWorld,
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

const TRACE = "support-pressure-100";

const WORKERS = [
  { id: "WRK-0001", team_id: "TEAM-SUPPORT", skills: ["general"], status: "busy", current_ticket_id: "TCK-1" },
  { id: "WRK-0002", team_id: "TEAM-SUPPORT", skills: ["billing"], status: "idle", current_ticket_id: null },
  { id: "WRK-0035", team_id: "TEAM-SUPPORT", skills: ["general"], status: "idle", current_ticket_id: null },
  { id: "WRK-0040", team_id: "TEAM-SUPPORT", skills: ["general"], status: "busy", current_ticket_id: "TCK-2" },
  { id: "WRK-0050", team_id: "TEAM-RESERVE", skills: ["general"], status: "reserve", current_ticket_id: null },
];

const TICKETS = [
  { id: "TCK-1", customer_id: "CUST-1", severity: "high" as const, required_skill: "general", status: "in_service" as const, assigned_worker_id: "WRK-0001", queued_at: 5, sla_deadline: 35, sla_breached: false },
  { id: "TCK-2", customer_id: "CUST-2", severity: "medium" as const, required_skill: "billing", status: "in_service" as const, assigned_worker_id: "WRK-0040", queued_at: 6, sla_deadline: 36, sla_breached: false },
  { id: "TCK-3", customer_id: "CUST-3", severity: "low" as const, required_skill: "general", status: "queued" as const, assigned_worker_id: null, queued_at: 10, sla_deadline: 40, sla_breached: false },
  { id: "TCK-4", customer_id: "CUST-4", severity: "high" as const, required_skill: "general", status: "queued" as const, assigned_worker_id: null, queued_at: 2, sla_deadline: 32, sla_breached: true },
  { id: "TCK-5", customer_id: "CUST-5", severity: "medium" as const, required_skill: "general", status: "resolved" as const, assigned_worker_id: "WRK-0001", queued_at: 1, sla_deadline: 31, sla_breached: false, resolved_at: 20 },
  { id: "TCK-6", customer_id: "CUST-6", severity: "low" as const, required_skill: "general", status: "abandoned" as const, assigned_worker_id: null, queued_at: 0, sla_deadline: 30, sla_breached: true, abandoned_at: 25 },
];

const EVENTS: WorldEvent[] = [
  ev(50, "ticket.queued", "TCK-3", "queue:support", null, "trace-q3"),
  ev(60, "sensor.tripped", "sensor:support_pressure", "queue:support", null, TRACE),
  ev(61, "responder.requested", null, null, "E-60", TRACE),
  ev(62, "responder.decided", null, null, "E-61", TRACE, { instance_id: "abc123def456", command: { type: "reallocate_workers" } }),
  ev(63, "command.accepted", "surge_staffing", "TEAM-SUPPORT", null, TRACE),
  ev(64, "worker.reallocated", "WRK-0035", "TEAM-SUPPORT", "E-63", TRACE),
  ev(65, "worker.reallocated", "WRK-0040", "TEAM-SUPPORT", "E-63", TRACE),
  ev(66, "ticket.resolved", "TCK-5", "CUST-5", null, "trace-t5"),
];

const BASE_STATE: WorldState = {
  enabled: true,
  scenario: "support",
  seed: 42,
  status: "running",
  sim_time: 66,
  latest_seq: 66,
  projection: {
    support_backlog: 2, tickets_in_service: 2, tickets_resolved: 1, tickets_abandoned: 1,
    tickets_opened: 6, workers_idle: 2, workers_busy: 2, sla_breach_pct: 0.33,
    average_wait_minutes: 4, customer_sentiment: 0.8, customer_churn_risk: 0.1,
  },
  customers: [{ id: "CUST-1" }],
  tickets: TICKETS,
  workers: WORKERS,
  teams: [
    { id: "TEAM-SUPPORT", name: "Support", worker_ids: ["WRK-0001", "WRK-0002", "WRK-0035", "WRK-0040"] },
    { id: "TEAM-RESERVE", name: "Reserve", worker_ids: ["WRK-0050"] },
  ],
  last_response: null,
};

function hook(over: Partial<UseWorldSimulationResult> = {}): UseWorldSimulationResult {
  return {
    state: BASE_STATE,
    events: EVENTS,
    loading: false,
    error: null,
    injectSurge: vi.fn(async () => {}),
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

describe("World route", () => {
  it("mounts the world route surface", () => {
    renderWorld();
    expect(screen.getByTestId("world-route")).toBeTruthy();
    // No aggregate KPI panel from the old constellation HUD.
    expect(screen.queryByTestId("world-signals-panel")).toBeNull();
  });

  it("renders real ticket IDs in the correct lanes", () => {
    renderWorld();
    const waiting = screen.getByTestId("lane-waiting");
    expect(within(waiting).getByText("TCK-3")).toBeTruthy();
    expect(within(waiting).getByText("TCK-4")).toBeTruthy();
    expect(within(waiting).queryByText("TCK-1")).toBeNull();

    const inService = screen.getByTestId("lane-in-service");
    expect(within(inService).getByText("TCK-1")).toBeTruthy();
    expect(within(inService).getByText("TCK-2")).toBeTruthy();

    const resolved = screen.getByTestId("lane-resolved");
    expect(within(resolved).getByText("TCK-5")).toBeTruthy();

    const abandoned = screen.getByTestId("lane-abandoned");
    expect(within(abandoned).getByText("TCK-6")).toBeTruthy();
  });

  it("shows the assigned worker ID on an in-service ticket and customer/skill on a waiting ticket", () => {
    renderWorld();
    const t1 = screen.getByTestId("ticket-TCK-1");
    expect(within(t1).getByText(/WRK-0001/)).toBeTruthy();
    const t3 = screen.getByTestId("ticket-TCK-3");
    expect(within(t3).getByText(/CUST-3/)).toBeTruthy();
    expect(within(t3).getByText(/general/)).toBeTruthy();
  });

  it("groups workers into support and reserve, busy showing the current ticket", () => {
    renderWorld();
    const support = screen.getByTestId("workers-support");
    expect(within(support).getByTestId("worker-WRK-0001")).toBeTruthy();
    expect(within(support).getByTestId("worker-WRK-0035")).toBeTruthy();
    expect(within(support).getByTestId("worker-WRK-0040")).toBeTruthy();

    const reserve = screen.getByTestId("workers-reserve");
    expect(within(reserve).getByTestId("worker-WRK-0050")).toBeTruthy();

    // Busy worker names its current ticket.
    const w1 = screen.getByTestId("worker-WRK-0001");
    expect(within(w1).getByText(/TCK-1/)).toBeTruthy();
  });

  it("renders the Durable intervention causal strip with the real trace and reallocated worker IDs", () => {
    renderWorld();
    const strip = screen.getByTestId("intervention");
    expect(within(strip).getByText(/Pressure detected/i)).toBeTruthy();
    expect(within(strip).getByText(/Responder requested/i)).toBeTruthy();
    expect(within(strip).getByText(/Durable decided/i)).toBeTruthy();
    expect(within(strip).getByText(/Command accepted/i)).toBeTruthy();
    // Actual reallocated worker IDs from worker.reallocated events.
    expect(within(strip).getByText(/WRK-0035/)).toBeTruthy();
    expect(within(strip).getByText(/WRK-0040/)).toBeTruthy();
    // The real journal trace id backs the strip.
    expect(within(strip).getByText(new RegExp(TRACE))).toBeTruthy();
    // The Durable instance id from responder.decided payload.
    expect(within(strip).getByText(/abc123def456/)).toBeTruthy();
  });

  it("hides the intervention strip when no responder events are present", () => {
    mockUseWorld.mockReturnValue(hook({ events: [ev(1, "ticket.queued", "TCK-9", "queue:support", null, "t")] }));
    renderWorld();
    expect(screen.queryByTestId("intervention")).toBeNull();
  });

  it("renders the recent event journal with actor and cause", () => {
    renderWorld();
    const journal = screen.getByTestId("event-journal");
    const row = within(journal).getByTestId("event-64");
    expect(within(row).getByText("worker.reallocated")).toBeTruthy();
    expect(within(row).getByText("WRK-0035")).toBeTruthy();
    expect(within(row).getByText(/E-63/)).toBeTruthy();
  });

  it("filters the journal when an actor is clicked", () => {
    renderWorld();
    const journal = screen.getByTestId("event-journal");
    // Before filtering, the reallocation event is visible.
    expect(within(journal).queryByTestId("event-64")).toBeTruthy();

    // Click the waiting ticket TCK-3 (an actor).
    fireEvent.click(screen.getByTestId("ticket-TCK-3"));

    const filtered = screen.getByTestId("event-journal");
    // Only TCK-3's own event remains; unrelated events are gone.
    expect(within(filtered).getByTestId("event-50")).toBeTruthy();
    expect(within(filtered).queryByTestId("event-64")).toBeNull();
  });

  it("invokes injectSurge when the single control is clicked", () => {
    const injectSurge = vi.fn(async () => {});
    mockUseWorld.mockReturnValue(hook({ injectSurge }));
    renderWorld();
    fireEvent.click(screen.getByTestId("inject-surge"));
    expect(injectSurge).toHaveBeenCalledTimes(1);
  });

  it("shows an explicit loading state before the first snapshot", () => {
    mockUseWorld.mockReturnValue(hook({ state: null, events: [], loading: true }));
    renderWorld();
    expect(screen.getByTestId("world-loading")).toBeTruthy();
  });

  it("shows an explicit error state", () => {
    mockUseWorld.mockReturnValue(hook({ error: "world state HTTP 500" }));
    renderWorld();
    expect(screen.getByTestId("world-error")).toBeTruthy();
    expect(screen.getByText(/world state HTTP 500/)).toBeTruthy();
  });

  it("shows a disabled state and disables the surge control when the world is off", () => {
    mockUseWorld.mockReturnValue(hook({ state: { enabled: false } }));
    renderWorld();
    expect(screen.getByTestId("world-disabled")).toBeTruthy();
    expect((screen.getByTestId("inject-surge") as HTMLButtonElement).disabled).toBe(true);
  });
});

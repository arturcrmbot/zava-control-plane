// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import SpatialWorld from "../SpatialWorld";

const scene = {
  version: "1",
  title: "Travel Operations",
  locations: [
    { id: "APT-LGW", label: "London Gatwick", x: 0.1, y: 0.2 },
    { id: "DST-PMI", label: "Palma de Mallorca", x: 0.8, y: 0.7 },
    { id: "HTL-SUN-PMI", label: "Sunseeker Palma Bay Resort", x: 0.85, y: 0.75 },
  ],
  actor_bindings: [
    { collection: "flights", kind: "flight", id_field: "id", state_field: "status", position: { route_field: "route_location_ids", progress_field: "progress" } },
    { collection: "transfers", kind: "transfer", id_field: "id", state_field: "status", position: { route_field: "route_location_ids", progress_field: "progress" } },
    { collection: "parties", kind: "party", id_field: "id", state_field: "state", position: { location_field: "current_location_id" } },
    { collection: "customers", kind: "customer", id_field: "id", state_field: "status", position: { location_field: "current_location_id" } },
    { collection: "staff", kind: "staff", id_field: "id", state_field: "last_action", position: { location_field: "current_location_id" } },
    { collection: "hotels", kind: "hotel", id_field: "id", state_field: "occupancy_status", position: { location_field: "id" } },
    { collection: "bookings", kind: "booking", id_field: "id", state_field: "status", position: { location_field: "current_location_id" } },
    { collection: "disruptions", kind: "disruption", id_field: "id", state_field: "status", position: { location_field: "current_location_id" } },
    { collection: "recovery_decisions", kind: "recovery", id_field: "id", state_field: "outcome", position: { location_field: "current_location_id" } },
    { collection: "workflow_runs", kind: "workflow", id_field: "id", state_field: "status", position: { location_field: "current_location_id" } },
  ],
  event_mappings: [
    { event_type: "workflow.auto_fired", animation_type: "state", actor_id_field: "actor_id" },
    { event_type: "flight.alert", animation_type: "alert", actor_id_field: "actor_id" },
  ],
};

const snapshot = {
  flights: [{ id: "FLT-ZV204", status: "cancelled", route_location_ids: ["APT-LGW", "DST-PMI"], progress: 0 }],
  transfers: [{ id: "TRF-4", status: "in_progress", route_location_ids: ["DST-PMI", "HTL-SUN-PMI"], progress: 0.5 }],
  parties: [{ id: "PTY-4", state: "reaccommodated", current_location_id: "HTL-SUN-PMI" }],
  customers: [{ id: "CUST-4", status: "informed", current_location_id: "HTL-SUN-PMI" }],
  staff: [{ id: "OPS-1", last_action: "rebooked", current_location_id: "APT-LGW" }],
  hotels: [{ id: "HTL-SUN-PMI", occupancy_status: "near_full", occupancy_ratio: 0.92, capacity_ratio: 0.96 }],
  bookings: [{ id: "BKG-4", status: "reaccommodated", current_location_id: "HTL-SUN-PMI" }],
  disruptions: [{ id: "DIS-FLT-ZV204", status: "open", current_location_id: "APT-LGW" }],
  recovery_decisions: [{ id: "DEC-4", outcome: "pending", current_location_id: "APT-LGW" }],
  workflow_runs: [{ id: "TRV-WF-9", status: "awaiting_hitl", current_location_id: "APT-LGW" }],
};

const events = [{
  seq: 19, event_id: "EVT-19", type: "workflow.auto_fired", actor_id: "TRV-WF-9", target_id: null,
  payload: { workflow_id: "TRV-WF-9" },
}, {
  seq: 20, event_id: "EVT-20", type: "flight.alert", actor_id: "FLT-ZV204", target_id: null,
  payload: {},
}];

const pendingDetail = {
  workflow: { id: "TRV-WF-9", type: "flight-disruption-recovery", status: "awaiting_hitl" },
  activeException: {
    id: "EXC-9",
    workflowId: "TRV-WF-9",
    summary: "Material recovery option needs approval",
    recommendation: "Approve the selected recovery option",
  },
  packDetail: {
    trigger: { evidence_event_ids: ["EVT-19"], booking_id: "BKG-4", measurements: { delay_minutes: 180 } },
    phases: [{ name: "detect", status: "completed" }, { name: "evaluate", status: "completed" }],
    skills: ["recovery-planner"],
    tools: ["capacity-search"],
    reasoning: { alternatives: ["ALT-1"], rationale: "keeps the party together", capacity: "2 seats", incremental_cost: 74, material_changes: ["flight"] },
    hitl: { required: true, outcome: "pending", required_role: "operations" },
    command: { type: "reaccommodate", command_id: "CMD-9" },
    evaluation: { status: "passed", criteria: "capacity remains valid" },
  },
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("SpatialWorld", () => {
  it("renders a spatial, journal-backed Travel-shaped world and opens its exact workflow detail", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(pendingDetail), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const ui = render(<MemoryRouter><SpatialWorld scene={scene} snapshot={snapshot} events={events} /></MemoryRouter>);

    expect(screen.getByText("London Gatwick")).toBeTruthy();
    expect(screen.getByText("Palma de Mallorca")).toBeTruthy();
    for (const id of ["FLT-ZV204", "TRF-4", "PTY-4", "CUST-4", "OPS-1", "HTL-SUN-PMI", "BKG-4", "DIS-FLT-ZV204", "DEC-4", "TRV-WF-9"]) {
      expect(screen.getByTestId(`scene-actor-${id}`)).toBeTruthy();
    }
    expect(screen.getByTestId("scene-actor-TRV-WF-9").getAttribute("data-animation")).toBe("state");
    expect(screen.getByTestId("scene-actor-HTL-SUN-PMI").textContent).toContain("near_full");
    expect(screen.getByTestId("scene-actor-HTL-SUN-PMI").textContent).toContain("occupancy ratio: 0.92");
    fireEvent.click(screen.getByTestId("scene-actor-FLT-ZV204"));
    expect(screen.getByTestId("scene-event-EVT-20")).toBeTruthy();
    expect(screen.queryByTestId("scene-event-EVT-19")).toBeNull();

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/workflows/TRV-WF-9", expect.anything()));
    const detail = screen.getByRole("region", { name: "Workflow detail" }).textContent;
    expect(screen.getByTestId("workflow-detail-status").textContent).toContain("awaiting_hitl");
    for (const evidence of ["delay minutes", "detect", "recovery-planner", "capacity-search", "alternatives", "rationale", "capacity", "incremental cost", "material changes", "hitl", "reaccommodate", "passed"]) {
      expect(detail).toContain(evidence);
    }
    const hitlAudit = screen.getByRole("region", { name: "HITL gate audit" }).textContent;
    for (const evidence of ["awaiting_hitl", "EXC-9", "Material recovery option needs approval"]) {
      expect(hitlAudit).toContain(evidence);
    }
    expect(screen.getByRole("button", { name: "Approve" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Decline" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /run.*process/i })).toBeNull();

    ui.rerender(
      <MemoryRouter>
        <SpatialWorld
          scene={scene}
          snapshot={{ ...snapshot, flights: [{ ...snapshot.flights[0], status: "departed", progress: 0.5 }] }}
          events={events}
        />
      </MemoryRouter>,
    );
    const movedFlight = screen.getByTestId("scene-actor-FLT-ZV204");
    expect(movedFlight.getAttribute("data-position")).toBe("0.45,0.45");
    expect(movedFlight.textContent).toContain("departed");
  });

  it("only exposes generic gate controls while a fetched gate is pending", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
      ...pendingDetail,
      packDetail: { ...pendingDetail.packDetail, hitl: { required: true, outcome: "approved" } },
    }), { status: 200 })));

    render(<MemoryRouter><SpatialWorld scene={scene} snapshot={snapshot} events={events} /></MemoryRouter>);

    await screen.findByRole("region", { name: "Workflow detail" });
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Decline" })).toBeNull();
  });

  it("refreshes the exact workflow detail after resolving its pending gate", async () => {
    const completedDetail = {
      ...pendingDetail,
      workflow: { ...pendingDetail.workflow, status: "completed" },
      activeException: null,
      packDetail: {
        ...pendingDetail.packDetail,
        hitl: { required: true, outcome: "approved" },
      },
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(pendingDetail), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(completedDetail), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<MemoryRouter><SpatialWorld scene={scene} snapshot={snapshot} events={events} /></MemoryRouter>);

    await screen.findByRole("button", { name: "Approve" });
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/exceptions/EXC-9/resolve",
      expect.objectContaining({ method: "POST" }),
    ));
    await waitFor(() => expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/workflows/TRV-WF-9",
    ));
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
    expect(screen.getByTestId("workflow-detail-status").textContent).toContain("completed");
  });

  it("opens the exact query-selected workflow before the journal carries its id", async () => {
    const workflowId = "fdr-exact-auto-fired";
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({
      ...pendingDetail,
      workflow: { ...pendingDetail.workflow, id: workflowId },
    }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter initialEntries={[`/world?workflow_id=${workflowId}`]}>
        <SpatialWorld scene={scene} snapshot={snapshot} events={[]} />
      </MemoryRouter>,
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      `/api/workflows/${workflowId}`,
      expect.anything(),
    ));
    expect(screen.getByRole("region", { name: "Workflow detail" }).textContent).toContain(workflowId);
  });
});

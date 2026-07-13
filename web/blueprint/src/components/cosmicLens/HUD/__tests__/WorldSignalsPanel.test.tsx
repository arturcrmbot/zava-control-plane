// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { WorldSignalsPanel } from "../WorldSignalsPanel";

function stubWorldState(body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(body), { status: 200 })),
  );
}

describe("WorldSignalsPanel", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders nothing when the engine is disabled", async () => {
    stubWorldState({ enabled: false });
    const { container } = render(<WorldSignalsPanel />);
    await waitFor(() => expect(fetch as unknown as ReturnType<typeof vi.fn>).toHaveBeenCalled());
    expect(container.querySelector('[data-testid="world-signals-panel"]')).toBeNull();
  });

  it("renders live world stats when enabled", async () => {
    stubWorldState({
      enabled: true,
      pack: "toy",
      stocks: { support_backlog: 150 },
      resources: { agents: 20 },
      signals: { sla_breach_pct: 0.79 },
      inputs: { ticket_arrival_rate: 90 },
      last_response: null,
    });
    render(<WorldSignalsPanel />);
    await waitFor(() => expect(screen.getByText("150")).toBeTruthy());
    expect(screen.getByText("79%")).toBeTruthy();
    expect(screen.getByText("20")).toBeTruthy();
    expect(screen.getByText(/responder idle/)).toBeTruthy();
  });

  it("shows the durable responder decision when present", async () => {
    stubWorldState({
      enabled: true,
      pack: "toy",
      stocks: { support_backlog: 0 },
      resources: { agents: 70 },
      signals: { sla_breach_pct: 0 },
      inputs: { ticket_arrival_rate: 30 },
      last_response: { instance_id: "0584ee2c888c45c49a99", hired: 50 },
    });
    render(<WorldSignalsPanel />);
    await waitFor(() => expect(screen.getByText(/\+50/)).toBeTruthy());
    expect(screen.getByText(/0584ee2c888c/)).toBeTruthy();
  });
});

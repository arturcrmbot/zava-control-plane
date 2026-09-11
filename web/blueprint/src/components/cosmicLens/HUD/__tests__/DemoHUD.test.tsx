// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { DemoHUD } from "../DemoHUD";

describe("DemoHUD", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ ok: true }), { status: 200 }),
      ),
    );
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders nothing when disabled", () => {
    const { container } = render(<DemoHUD enabled={false} />);
    expect(container.childElementCount).toBe(0);
  });

  it("renders the launcher when enabled", () => {
    render(<DemoHUD enabled={true} />);
    expect(screen.getByText(/Demo Controls/i)).toBeTruthy();
  });

  it("expands and triggers scenarios", async () => {
    render(<DemoHUD enabled={true} />);
    fireEvent.click(screen.getByText(/Demo Controls/i));
    const scenario = screen.getByText(/Aurora Budget Overrun/i).parentElement!;
    fireEvent.click(within(scenario).getByRole("button", { name: /^Trigger$/i }));
    await waitFor(() => {
      expect(screen.getByText(/Triggered\./i)).toBeTruthy();
    });
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/demo/trigger/aurora-overrun"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("opens the real accepted Aurora workflow instead of a caption script", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(Response.json(
      { workflow_id: "AUR-real" }, { status: 202 },
    ));
    const onFollow = vi.fn();
    render(<DemoHUD enabled={true} onFollow={onFollow} />);
    fireEvent.click(screen.getByText(/Demo Controls/i));
    const scenario = screen.getByText("Start Aurora budget response").parentElement!;
    fireEvent.click(within(scenario).getByRole("button", { name: /^Trigger$/i }));
    await waitFor(() => expect(onFollow).toHaveBeenCalledWith({
      workflowId: "AUR-real", source: "live",
    }));
    expect(fetch).toHaveBeenCalledWith(
      "/api/demo/trigger/full-aurora-arc?count=3",
      { method: "POST", headers: { "Idempotency-Key": expect.any(String) } },
    );
  });

  it("shows partial invoice-batch results in the actual batch caller", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(Response.json({
      detail: {
        message: "Batch incomplete",
        started_workflow_ids: ["API-confirmed"],
        unconfirmed_workflow_id: "API-unconfirmed",
        unconfirmed_instance_id: "instance-unconfirmed",
        requested_count: 3,
        failed_item: 2,
      },
    }, { status: 503 }));
    render(<DemoHUD enabled={true} />);
    fireEvent.click(screen.getByText(/Demo Controls/i));
    const scenario = screen.getByText("Queue Aurora invoices").parentElement!;
    fireEvent.click(within(scenario).getByRole("button", { name: /^Trigger$/i }));
    await waitFor(() => {
      expect(screen.getByText(/Batch incomplete.*API-confirmed.*API-unconfirmed/)).toBeTruthy();
    });
  });
});

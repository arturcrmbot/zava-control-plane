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
});

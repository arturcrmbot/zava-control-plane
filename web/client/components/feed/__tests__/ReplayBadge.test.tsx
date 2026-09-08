// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { ReplayBadge } from "@client/components/feed/ReplayBadge";

beforeEach(() => {
  globalThis.fetch = vi.fn();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ReplayBadge", () => {
  it("renders nothing in live mode", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ mode: "live" }),
    } as Response);

    const { container } = render(<ReplayBadge />);

    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledTimes(1));
    expect(container.firstChild).toBeNull();
  });

  it("renders the replay pill and opens the modal in replay mode", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue({
      ok: true,
      json: async () => ({
        mode: "replay",
        recorded_at: "2026-05-22T12:00:00.000Z",
        selected_vertical: "agency",
        active_vertical: "agency",
        pack_matches_tape: true,
      }),
    } as Response);

    render(<ReplayBadge />);

    const pill = await screen.findByRole("button", { name: /recorded replay.*agency.*2026/i });
    expect(pill).toBeTruthy();

    fireEvent.click(pill);

    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByText(/you're watching a replay/i)).toBeTruthy();
    expect(screen.getByText("Agency")).toBeTruthy();
    expect(screen.getAllByText(/May 22, 2026|22 May 2026/).length).toBeGreaterThan(0);
    expect(screen.getByText(/buttons you see are real but disabled/i)).toBeTruthy();
  });

  it("warns when the running pack does not match the recorded vertical", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue({
      ok: true,
      json: async () => ({
        mode: "replay",
        recorded_at: "2026-08-10T09:00:00.000Z",
        selected_vertical: "telco",
        active_vertical: "agency",
        pack_matches_tape: false,
      }),
    } as Response);

    render(<ReplayBadge />);
    fireEvent.click(await screen.findByRole("button", { name: /recorded replay.*telco/i }));

    expect(screen.getByRole("alert").textContent).toMatch(/recorded for telco/i);
    expect(screen.getByRole("alert").textContent).toMatch(/running pack is agency/i);
    expect(screen.queryByText(/live replay/i)).toBeNull();
  });
});

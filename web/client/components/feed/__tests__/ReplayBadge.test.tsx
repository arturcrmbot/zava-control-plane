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
      json: async () => ({ mode: "replay", recorded_at: "2026-05-22T12:00:00.000Z" }),
    } as Response);

    render(<ReplayBadge />);

    const pill = await screen.findByRole("button", { name: /live replay — recorded/i });
    expect(pill).toBeTruthy();

    fireEvent.click(pill);

    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByText(/you're watching a replay/i)).toBeTruthy();
    expect(screen.getByText(/buttons you see are real but disabled/i)).toBeTruthy();
  });
});

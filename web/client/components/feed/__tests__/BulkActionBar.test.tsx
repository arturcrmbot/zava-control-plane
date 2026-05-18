// @vitest-environment jsdom
// web/client/components/feed/__tests__/BulkActionBar.test.tsx
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import BulkActionBar from "@client/components/feed/BulkActionBar";

beforeEach(() => {
  globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) } as Response);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("BulkActionBar", () => {
  it("renders the count and 4 actions when items are selected", () => {
    render(<BulkActionBar selectedIds={["hitl:WF-1", "hitl:WF-2"]} onCleared={() => {}} />);
    expect(screen.getByText(/2 selected/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Approve/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Reject/i })).toBeTruthy();
  });

  it("renders nothing when no items are selected", () => {
    const { container } = render(<BulkActionBar selectedIds={[]} onCleared={() => {}} />);
    expect(container.firstChild).toBeNull();
  });

  it("POSTs to /api/exceptions/bulk-resolve and clears selection on Approve", async () => {
    const onCleared = vi.fn();
    render(<BulkActionBar selectedIds={["exception:E1", "exception:E2"]} onCleared={onCleared} />);
    fireEvent.click(screen.getByRole("button", { name: /Approve/i }));
    await waitFor(() => {
      expect((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
        "/api/exceptions/bulk-resolve",
      );
    });
    expect(onCleared).toHaveBeenCalled();
  });
});

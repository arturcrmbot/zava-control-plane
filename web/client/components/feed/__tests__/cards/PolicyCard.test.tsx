// @vitest-environment jsdom
// web/client/components/feed/__tests__/cards/PolicyCard.test.tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import PolicyCard from "@client/components/feed/cards/PolicyCard";
import type { PolicyItem } from "@shared/feedItems";

afterEach(cleanup);

const item: PolicyItem = {
  type: "policy", id: "policy:P-1:abc", timestamp: 100,
  policyId: "autonomy.threshold.vendor-kyc", severity: null,
  description: "Autonomy threshold for vendor-kyc",
  currentValue: 0.85, actor: "alice@zava",
};

describe("PolicyCard", () => {
  it("renders the description, actor and current value", () => {
    render(<MemoryRouter><PolicyCard item={item} /></MemoryRouter>);
    expect(screen.getByText(/Autonomy threshold for vendor-kyc/)).toBeTruthy();
    expect(screen.getByText(/alice@zava/)).toBeTruthy();
    expect(screen.getByText(/0\.85/)).toBeTruthy();
  });
  it("Acknowledge button hides the card locally", () => {
    render(<MemoryRouter><PolicyCard item={item} /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: /Acknowledge/i }));
    expect(screen.queryByText(/Autonomy threshold for vendor-kyc/)).toBeNull();
  });
  it("View diff calls onOpenDrawer with the policyId", () => {
    const onOpen = vi.fn();
    render(<MemoryRouter><PolicyCard item={item} onOpenDrawer={onOpen} /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: /View diff/i }));
    expect(onOpen).toHaveBeenCalledWith("autonomy.threshold.vendor-kyc");
  });
});

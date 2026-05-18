// @vitest-environment jsdom
// web/client/components/feed/__tests__/Header.test.tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Header from "@client/components/feed/Header";
import { getRolePreset } from "@shared/roles";
import type { FeedItem } from "@shared/feedItems";

afterEach(cleanup);

const noop = () => {};
const items: FeedItem[] = [];
const role = getRolePreset("ops-reviewer");

describe("Header", () => {
  it("renders the Apex brand link", () => {
    render(<MemoryRouter><Header role={role} onRoleChange={noop} unreadItems={items} onJumpTo={noop} onSearch={noop} workflows={[]} /></MemoryRouter>);
    expect(screen.getByText(/Apex/i)).toBeTruthy();
  });
  it("renders Today chip per role (ops-reviewer flavour)", () => {
    render(<MemoryRouter><Header role={role} onRoleChange={noop} unreadItems={items} onJumpTo={noop} onSearch={noop} workflows={[]} /></MemoryRouter>);
    expect(screen.getByText(/Today:/i)).toBeTruthy();
  });
  it("search popover shows matching workflow ids and fires onSearch", () => {
    const onSearch = vi.fn();
    render(<MemoryRouter><Header role={role} onRoleChange={noop} unreadItems={items} onJumpTo={noop} onSearch={onSearch}
      workflows={[
        { id: "WF-1", type: "expense-claim", status: "in_progress", currentPhase: "Intake",
          createdAt: 1, slaDueAt: 1, jurisdiction: "UK", agency: "Z",
          actionLedger: [], tokensSpent: 0, costUSD: 0 },
        { id: "WF-2", type: "hiring", status: "in_progress", currentPhase: "Sourcing",
          createdAt: 1, slaDueAt: 1, jurisdiction: "UK", agency: "Z",
          actionLedger: [], tokensSpent: 0, costUSD: 0 },
      ]} /></MemoryRouter>);
    fireEvent.change(screen.getByPlaceholderText(/search workflows/i), { target: { value: "wf-1" } });
    expect(screen.getByRole("button", { name: /WF-1/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /WF-1/ }));
    expect(onSearch).toHaveBeenCalledWith("WF-1");
  });
});

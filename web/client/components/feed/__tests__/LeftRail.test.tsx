// @vitest-environment jsdom
// web/client/components/feed/__tests__/LeftRail.test.tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("@client/hooks/useRuntimeManifest", () => ({
  useRuntimeManifest: () => ({
    loading: false,
    error: null,
    manifest: {
      vertical: { name: "agency", display_name: "Agency" },
      world: null,
      capabilities: ["blueprint", "compose", "knowledge", "memory"],
      ui: { lenses: ["agency-operations"], theme: {} },
    },
  }),
}));

import LeftRail from "@client/components/feed/LeftRail";
import { getRolePreset } from "@shared/roles";

afterEach(cleanup);

describe("LeftRail", () => {
  it("renders role-default saved views", () => {
    render(<MemoryRouter><LeftRail role={getRolePreset("ops-reviewer")} userViews={[]} onSelectView={() => {}} onSaveCurrent={() => {}} /></MemoryRouter>);
    expect(screen.getByText(/Critical · needs you/i)).toBeTruthy();
  });
  it("renders the More ▾ submenu with the 4 demoted routes", () => {
    render(<MemoryRouter><LeftRail role={getRolePreset("ops-reviewer")} userViews={[]} onSelectView={() => {}} onSaveCurrent={() => {}} /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: /More/i }));
    expect(screen.getByText(/Analytics/i)).toBeTruthy();
    expect(screen.getByText(/Evaluations/i)).toBeTruthy();
    expect(screen.getByText(/Economics/i)).toBeTruthy();
    expect(screen.getByText(/Policy/i)).toBeTruthy();
  });
  it("renders the Constellation external link", () => {
    render(<MemoryRouter><LeftRail role={getRolePreset("ops-reviewer")} userViews={[]} onSelectView={() => {}} onSaveCurrent={() => {}} /></MemoryRouter>);
    expect(screen.getByText(/Constellation/i)).toBeTruthy();
  });
  it("fires onSelectView when a saved view is clicked", () => {
    const onSel = vi.fn();
    render(<MemoryRouter><LeftRail role={getRolePreset("ops-reviewer")} userViews={[]} onSelectView={onSel} onSaveCurrent={() => {}} /></MemoryRouter>);
    fireEvent.click(screen.getByText(/Critical · needs you/i));
    expect(onSel).toHaveBeenCalled();
  });
});

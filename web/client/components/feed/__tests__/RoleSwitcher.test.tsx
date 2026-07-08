// @vitest-environment jsdom
// web/client/components/feed/__tests__/RoleSwitcher.test.tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import RoleSwitcher from "@client/components/feed/RoleSwitcher";
import { ROLE_PRESETS } from "@shared/roles";

afterEach(cleanup);

describe("RoleSwitcher", () => {
  it("renders the current role label", () => {
    render(<RoleSwitcher current="ops-reviewer" onChange={() => {}} />);
    expect(screen.getByText(/System Admin/i)).toBeTruthy();
  });
  it("lists all 5 roles when opened and fires onChange on select", () => {
    const onChange = vi.fn();
    render(<RoleSwitcher current="ops-reviewer" onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: /System Admin/i }));
    for (const r of ROLE_PRESETS) {
      expect(screen.getAllByText(new RegExp(r.label)).length).toBeGreaterThan(0);
    }
    fireEvent.click(screen.getByRole("menuitem", { name: /Executive/i }));
    expect(onChange).toHaveBeenCalledWith("executive");
  });
});

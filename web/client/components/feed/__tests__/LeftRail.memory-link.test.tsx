// @vitest-environment jsdom
// web/client/components/feed/__tests__/LeftRail.memory-link.test.tsx
import { describe, expect, it, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import LeftRail from "@client/components/feed/LeftRail";
import { getRolePreset } from "@shared/roles";

afterEach(cleanup);

describe("LeftRail Memory link", () => {
  it("renders a Memory link pointing to /memory", () => {
    render(
      <MemoryRouter>
        <LeftRail
          role={getRolePreset("ops-reviewer")}
          userViews={[]}
          onSelectView={() => {}}
          onSaveCurrent={() => {}}
        />
      </MemoryRouter>,
    );
    const link = screen.getByRole("link", { name: /Memory/i });
    expect(link.getAttribute("href")).toBe("/memory");
  });
});

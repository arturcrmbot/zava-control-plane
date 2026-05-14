// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

vi.mock("@react-three/fiber", () => ({
  Canvas: ({ children }: { children: ReactNode }) => <>{children}</>,
  // No-op mock — Cities calls useFrame for camera-distance LOD; tests
  // never tick the R3F clock, so we just register the callback and forget.
  useFrame: () => undefined,
}));
vi.mock("@react-three/drei", () => ({
  Html: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

import { Cities } from "../Cities";
import type { CityMeta, PersonaState } from "../lib/types";

const cities: CityMeta[] = [
  { id: "cpo", kind: "persona", label: "cpo", count: 0, active: true },
  { id: "tool.fetch_invoice", kind: "skill", label: "tool.fetch_invoice", active: true },
];

const personas: PersonaState[] = [
  { role: "cpo", state: "awaiting", pending_count: 2, last_decision: null },
];

describe("Cities", () => {
  it("renders persona city with the humanized job title from PERSONA_LABELS", () => {
    render(
      <Cities
        cities={cities}
        mode="capabilities"
        personas={personas}
      />,
    );
    // prettyActor("cpo") -> "Chief Procurement Officer"
    expect(screen.getByText(/Chief Procurement Officer/)).toBeTruthy();
    // Pending-count badge for HITL persona.
    expect(screen.getByText("2")).toBeTruthy();
  });
});

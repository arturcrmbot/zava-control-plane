// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { useRef } from "react";
import { render, screen } from "@testing-library/react";
import { KnowledgePulse } from "../KnowledgePulse";
import type { CosmicFlash, PulseSnapshot } from "../../lib/types";

function Harness({ pulse }: { pulse: PulseSnapshot | null }) {
  const flashesRef = useRef<{ buffer: CosmicFlash[]; version: number }>({
    buffer: [],
    version: 0,
  });
  return (
    <KnowledgePulse pulse={pulse} flashesRef={flashesRef} onOpenEntity={() => {}} />
  );
}

describe("KnowledgePulse", () => {
  it("renders humanized stat titles and the cross-domain heading", () => {
    const pulse: PulseSnapshot = {
      total: 42,
      growth_60s: 3,
      decisions_per_min: 1.5,
      links_per_min: 2.25,
      cross_domain_top: [
        { id: "VEN-0001", kind: "Vendor", workflow_count: 4, workflow_types_count: 2 },
      ],
    };
    render(<Harness pulse={pulse} />);
    // Humanized stat title shipped by Track F.
    expect(screen.getByText("Total records")).toBeTruthy();
    expect(screen.getByText("Records that span several teams")).toBeTruthy();
    // Pluralized humanized counts in cross-domain panel.
    expect(screen.getByText(/2 domains · 4 workflows/)).toBeTruthy();
    // The total value is rendered.
    expect(screen.getByText("42")).toBeTruthy();
  });

  it("renders empty-state copy when there is no pulse data", () => {
    render(<Harness pulse={null} />);
    expect(screen.getByText("nothing crosses domains yet")).toBeTruthy();
  });
});

// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { useRef } from "react";
import type { ReactNode } from "react";

vi.mock("@react-three/fiber", () => ({
  Canvas: ({ children }: { children: ReactNode }) => <>{children}</>,
  // useFrame is a no-op in jsdom — no render loop, no THREE camera.
  useFrame: () => {},
}));
vi.mock("@react-three/drei", () => ({
  Html: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

import { Rockets } from "../Rockets";
import { RocketRegistry, TrailRegistry } from "../lib/registries";
import { ExhaustRegistry } from "../RocketExhaust";
import type { CityMeta, CosmicFlash, FunctionMeta, Rocket } from "../lib/types";

function Harness() {
  const flashesRef = useRef<{ buffer: CosmicFlash[]; version: number }>({
    buffer: [],
    version: 0,
  });
  const rocketRegistry = useRef(new RocketRegistry()).current;
  const trailRegistry = useRef(new TrailRegistry()).current;
  const exhaustRegistry = useRef(new ExhaustRegistry()).current;

  // Seed a single rocket so Rockets.values() is non-empty at first render.
  const rocket: Rocket = {
    id: "VKY-0042",
    workflow_id: "VKY-0042",
    origin_workflow_id: "VKY-0042",
    phase: "idle",
    color: "#22d3ee",
    current_city_id: null,
    target_city_id: null,
    current_pos: [0, 0, 0],
    travel_from: null,
    travel_to: null,
    phase_started_at: Date.now(),
    spawned_at: Date.now(),
    is_wounded: false,
    last_label: "Reviewing vendor KYC",
  };
  rocketRegistry.set(rocket.id, rocket);

  const cities: CityMeta[] = [];
  const functions: FunctionMeta[] = [];

  return (
    <Rockets
      flashesRef={flashesRef}
      inFlight={[]}
      cities={cities}
      functions={functions}
      mode="capabilities"
      trailRegistry={trailRegistry}
      exhaustRegistry={exhaustRegistry}
      rocketRegistry={rocketRegistry}
    />
  );
}

describe("Rockets", () => {
  it("renders a rocket mesh and shows workflow label on hover", () => {
    const { container } = render(<Harness />);
    // R3F mesh JSX renders as lowercase host elements under jsdom.
    const meshes = container.querySelectorAll("mesh");
    expect(meshes.length).toBeGreaterThan(0);

    // Trigger hover to surface the humanized label tooltip.
    fireEvent.pointerOver(meshes[0]);
    expect(screen.getByText("VKY-0042")).toBeTruthy();
    expect(screen.getByText("Reviewing vendor KYC")).toBeTruthy();
  });
});

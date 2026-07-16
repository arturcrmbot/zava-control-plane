// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("../../lib/useComposition", () => ({
  useComposition: () => ({
    data: {
      vertical: {
        name: "telco",
        display_name: "Telco",
        manifest_version: "1",
        fingerprint: "telco:1",
      },
      skills: [],
      mcps: [],
      domains: [],
      meta_skills: [],
      workflow_types: {},
      phase_aliases: {},
      counts: {
        skills: 0,
        mcps: 0,
        domains_live: 0,
        domains_aspirational: 0,
      },
    },
  }),
}));
vi.mock("../../components/CompositionMap", () => ({
  CompositionMap: () => <div />,
}));

import { Composition } from "../Composition";

it("names the active vertical", () => {
  render(<Composition />);

  expect(screen.getByText(/Telco organisation/)).toBeTruthy();
});

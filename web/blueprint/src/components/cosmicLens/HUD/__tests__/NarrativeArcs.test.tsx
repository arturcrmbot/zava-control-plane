// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NarrativeArcs } from "../NarrativeArcs";

const SAMPLE = [
  {
    employee_id: "PERSON-EMP-0003",
    name: "Aisha Khan",
    role: "finance_bp",
    photo_url: "/assets/personae/aisha.png",
    one_liner: "Finance BP, over-promoted into a regional role",
    arc: "After two strong cycles she is one bad quarter from a downgrade.",
    function: "finance",
  },
  {
    employee_id: "PERSON-EMP-0011",
    name: "Marcus Holt",
    role: "cfo",
    photo_url: "/assets/personae/marcus.png",
    one_liner: "New CFO mid-restructure, aggressive on cost",
    arc: "Six weeks in, mandate to cut 12% from run-rate.",
    function: "finance",
  },
];

describe("NarrativeArcs", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => cleanup());

  function renderExpanded() {
    render(<NarrativeArcs initialArcs={SAMPLE} />);
    fireEvent.click(screen.getByTitle("Expand"));
  }

  it("renders one card per arc with name, role, and one-liner", () => {
    renderExpanded();
    expect(screen.getAllByText("Aisha Khan").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Marcus Holt").length).toBeGreaterThan(0);
    expect(screen.getByText("finance_bp")).toBeTruthy();
    expect(screen.getByText("cfo")).toBeTruthy();
    expect(
      screen.getByText("Finance BP, over-promoted into a regional role"),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: /Cast/i })).toBeTruthy();
  });

  it("renders initials avatars when no real photo asset is wired up", () => {
    renderExpanded();
    expect(screen.getByText("AK")).toBeTruthy();
    expect(screen.getByText("MH")).toBeTruthy();
  });

  it("toggles the card list from the collapsible header", () => {
    renderExpanded();
    expect(screen.getAllByText("Aisha Khan").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByTitle("Collapse"));
    expect(screen.queryByText("Aisha Khan")).toBeNull();
    fireEvent.click(screen.getByTitle("Expand"));
    expect(screen.getAllByText("Aisha Khan").length).toBeGreaterThan(0);
  });
});

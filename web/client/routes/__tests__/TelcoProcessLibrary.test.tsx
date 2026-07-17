// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import TelcoProcessLibrary from "../TelcoProcessLibrary";
import type {
  TelcoProcessCase,
  TelcoProcessSummary,
} from "@client/hooks/useWorldSimulation";


const PROCESSES: TelcoProcessSummary[] = Array.from(
  { length: 37 },
  (_, index) => ({
    source_id: `${index < 20 ? "OSS" : "BSS"}-${String(index + 1).padStart(2, "0")}`,
    workflow_type: `workflow-${index + 1}`,
    display_name: `Process ${index + 1}`,
    function: index % 2 === 0 ? "network-operations" : "customer-success",
    maturity: index < 9 ? "hero" : "standard",
    engine: index < 9 ? "hero" : "DDA",
    skills: index < 9 ? [] : ["evidence-correlator"],
    mcp_packs: index < 9 ? [] : ["network"],
  }),
);
const CASES: TelcoProcessCase[] = [
  {
    id: "CASE-001",
    workflow_type: "workflow-10",
    subject_ids: ["SITE-01"],
    status: "open",
    facts: { risk_score: 0.8 },
    allowed_actions: ["apply_action"],
    outcome: null,
  },
];

afterEach(cleanup);


describe("TelcoProcessLibrary", () => {
  it("renders all 37 registry-backed process cards", () => {
    render(
      <TelcoProcessLibrary
        processes={PROCESSES}
        cases={CASES}
        onRun={vi.fn(async () => {})}
      />,
    );

    expect(screen.getAllByTestId("telco-process-card")).toHaveLength(37);
    expect(screen.getByText("9 hero · 28 standard")).toBeTruthy();
  });

  it("filters process cards by catalogue and maturity", () => {
    render(
      <TelcoProcessLibrary
        processes={PROCESSES}
        cases={CASES}
        onRun={vi.fn(async () => {})}
      />,
    );

    fireEvent.change(screen.getByLabelText("Catalogue"), {
      target: { value: "BSS" },
    });
    expect(screen.getAllByTestId("telco-process-card")).toHaveLength(17);

    fireEvent.change(screen.getByLabelText("Maturity"), {
      target: { value: "standard" },
    });
    expect(screen.getAllByTestId("telco-process-card")).toHaveLength(17);
  });

  it("runs a standard process and shows its live case", () => {
    const onRun = vi.fn(async () => {});
    render(
      <TelcoProcessLibrary
        processes={PROCESSES}
        cases={CASES}
        onRun={onRun}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Run Process 10" }),
    );

    expect(onRun).toHaveBeenCalledWith("workflow-10");
    expect(screen.getByText("CASE-001 · open")).toBeTruthy();
  });
});

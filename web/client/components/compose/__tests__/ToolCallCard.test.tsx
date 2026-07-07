// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ToolCallCard } from "../ToolCallCard";

describe("ToolCallCard", () => {
  it("renders an edit card with a diff", () => {
    render(<ToolCallCard tool={{ id: "t1", title: "Creating x.py", kind: "edit", status: "completed", diff: { old: "", new: "# hi" } }} />);
    expect(screen.getByText("Creating x.py")).toBeTruthy();
    expect(screen.getByText("# hi")).toBeTruthy();
  });

  it("renders an execute card with output", () => {
    render(<ToolCallCard tool={{ id: "t2", title: "graduate.sh", kind: "execute", status: "running", output: "step 1..." }} />);
    expect(screen.getByText("step 1...")).toBeTruthy();
  });
});

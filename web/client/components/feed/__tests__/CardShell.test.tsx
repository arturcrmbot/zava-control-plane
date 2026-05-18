// @vitest-environment jsdom
// web/client/components/feed/__tests__/CardShell.test.tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import CardShell from "@client/components/feed/CardShell";

afterEach(cleanup);

describe("CardShell", () => {
  it("renders header, body, and action slots", () => {
    render(
      <CardShell
        severity="high"
        icon={<span data-testid="ic" />}
        typeLabel="HITL"
        workflowId="WF-1"
        timestampSec={Math.floor(Date.now() / 1000)}
        body={<div data-testid="body">body</div>}
        actions={<button data-testid="act">do</button>}
      />,
    );
    expect(screen.getByText("HITL")).toBeTruthy();
    expect(screen.getByText("WF-1")).toBeTruthy();
    expect(screen.getByTestId("body")).toBeTruthy();
    expect(screen.getByTestId("act")).toBeTruthy();
    expect(screen.getByTestId("ic")).toBeTruthy();
  });

  it("applies the severity border accent", () => {
    const { container } = render(
      <CardShell severity="critical" icon={null} typeLabel="X" workflowId="W" timestampSec={1}
        body={null} actions={null} />,
    );
    expect(container.querySelector(".border-l-4.border-red-500")).toBeTruthy();
  });

  it("uses slate accent for null severity", () => {
    const { container } = render(
      <CardShell severity={null} icon={null} typeLabel="X" workflowId="W" timestampSec={1}
        body={null} actions={null} />,
    );
    expect(container.querySelector(".border-l-4.border-slate-200")).toBeTruthy();
  });

  it("declares an @container scope so children can react to inline width", () => {
    const { container } = render(
      <CardShell severity="medium" icon={null} typeLabel="X" workflowId="W" timestampSec={1}
        body={null} actions={null} />,
    );
    const root = container.firstChild as HTMLElement;
    expect(root.className).toMatch(/@container/);
  });
});
